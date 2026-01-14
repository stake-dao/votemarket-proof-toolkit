"""
Eligibility service for determining which users can claim rewards.

This service identifies users who are eligible to claim VoteMarket rewards
based on their voting activity and current voting power.
"""

from typing import List, Optional

from eth_utils import to_checksum_address
from w3multicall.multicall import W3Multicall

from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.logging import get_logger
from votemarket_toolkit.shared.results import (
    ErrorSeverity,
    ProcessingError,
    Result,
)
from votemarket_toolkit.shared.retry import RPC_RETRY_CONFIG, retry_sync_operation
from votemarket_toolkit.shared.services.web3_service import Web3Service

_logger = get_logger(__name__)
from votemarket_toolkit.shared.types import EligibleUser
from votemarket_toolkit.utils.blockchain import get_rounded_epoch
from votemarket_toolkit.votes.services.votes_service import votes_service

MAX_UINT256 = (2**256) - 1


class EligibilityService:
    """
    Service for checking user eligibility to claim VoteMarket rewards.

    This service determines which users have active votes and are eligible
    to claim rewards for specific gauges and epochs.
    """

    def __init__(self, chain_id: int):
        """
        Initialize the eligibility service.

        Args:
            chain_id: Blockchain network ID (1 for Ethereum, 42161 for Arbitrum)
        """
        self.chain_id = chain_id
        self.web3_service = Web3Service.get_instance(chain_id)

    async def get_eligible_users(
        self,
        protocol: str,
        gauge_address: str,
        current_epoch: int,
        block_number: int,
        chain_id: Optional[int] = None,
        platform: Optional[str] = None,
    ) -> Result[List[EligibleUser]]:
        """
        Identify users who are eligible to claim rewards for a gauge/epoch.

        Returns users who meet ALL eligibility criteria:
        1. User voted for the gauge before the epoch (last_vote < current_epoch)
        2. Vote is still active at the epoch (end > current_epoch)
        3. User has positive voting power (slope > 0)

        Args:
            protocol: Protocol name ("curve", "balancer", "frax", "pendle", "yb")
            gauge_address: Address of the gauge to check
            current_epoch: Timestamp of the epoch to check eligibility for
            block_number: Block number to query at
            chain_id: Optional - if provided with platform, fetches canonical block from oracle
            platform: Optional - VoteMarket platform address for oracle lookup

        Returns:
            Result[List[EligibleUser]]: Success with eligible users, or failure with error

        Example:
            >>> result = await service.get_eligible_users(
            ...     protocol="curve",
            ...     gauge_address="0x7E1444BA99dcdFfE8fBdb42C02fb0DA4",
            ...     current_epoch=1699920000,
            ...     block_number=18500000
            ... )
            >>> if result.success:
            ...     for user in result.data:
            ...         print(user)
        """
        # Always round epoch to the day for consistency
        current_epoch = get_rounded_epoch(current_epoch)

        context = {
            "protocol": protocol,
            "gauge": gauge_address,
            "epoch": current_epoch,
            "block": block_number,
        }

        try:
            w3 = self.web3_service.w3

            # If chain and platform provided, fetch the canonical block number from oracle
            if chain_id is not None and platform is not None:
                from votemarket_toolkit.data.oracle import OracleService

                oracle_service = OracleService(self.chain_id)
                epoch_blocks = oracle_service.get_epochs_block(
                    chain_id, platform, [current_epoch]
                )
                block_number = epoch_blocks[current_epoch]
                if block_number == 0:
                    return Result.fail(
                        ProcessingError(
                            source="eligibility_service",
                            message=f"No block set for epoch {current_epoch}",
                            severity=ErrorSeverity.ERROR,
                            context=context,
                        )
                    )

            # Initialize multicall for efficient batch queries
            multicall = W3Multicall(w3)

            # Get the gauge controller contract address for this protocol
            gauge_controller = registry.get_gauge_controller(protocol)
            if not gauge_controller:
                return Result.fail(
                    ProcessingError(
                        source="eligibility_service",
                        message=f"No gauge controller found for protocol: {protocol}",
                        severity=ErrorSeverity.ERROR,
                        context=context,
                    )
                )
            gauge_controller_address = to_checksum_address(gauge_controller)

            # Step 1: Get all users who have EVER voted on this gauge
            gauge_votes = await votes_service.get_gauge_votes(
                protocol, gauge_address, block_number
            )
            unique_users = list(set(vote.user for vote in gauge_votes.votes))

            # Step 2: Query current vote status for each historical voter
            for user in unique_users:
                if protocol == "pendle":
                    # Pendle uses different contract interface
                    multicall.add(
                        W3Multicall.Call(
                            gauge_controller_address,
                            "getUserPoolVote(address,address)(uint256,uint256,uint256)",
                            [
                                to_checksum_address(user),
                                to_checksum_address(gauge_address),
                            ],
                        )
                    )
                    # Also get vote end time from veToken position
                    ve_address = registry.get_ve_address(protocol)
                    if ve_address:
                        multicall.add(
                            W3Multicall.Call(
                                to_checksum_address(ve_address),
                                "positionData(address)(uint128,uint128)",
                                [to_checksum_address(user)],
                            )
                        )
                elif protocol == "yb":
                    # YB uses different vote_user_slopes signature
                    multicall.add(
                        W3Multicall.Call(
                            gauge_controller_address,
                            "last_user_vote(address,address)(uint256)",
                            [
                                to_checksum_address(user),
                                to_checksum_address(gauge_address),
                            ],
                        )
                    )
                    # YB returns (slope, bias, power, end)
                    multicall.add(
                        W3Multicall.Call(
                            gauge_controller_address,
                            "vote_user_slopes(address,address)(uint256,uint256,uint256,uint256)",
                            [
                                to_checksum_address(user),
                                to_checksum_address(gauge_address),
                            ],
                        )
                    )
                else:
                    # Curve/Balancer/Frax use standard gauge controller interface
                    # Get last vote timestamp
                    multicall.add(
                        W3Multicall.Call(
                            gauge_controller_address,
                            "last_user_vote(address,address)(uint256)",
                            [
                                to_checksum_address(user),
                                to_checksum_address(gauge_address),
                            ],
                        )
                    )
                    # Get vote slopes: (slope, power, end_timestamp)
                    multicall.add(
                        W3Multicall.Call(
                            gauge_controller_address,
                            "vote_user_slopes(address,address)(int128,int128,uint256)",
                            [
                                to_checksum_address(user),
                                to_checksum_address(gauge_address),
                            ],
                        )
                    )

            # Step 3: Execute all queries in a single RPC call for efficiency
            # Use retry for transient RPC failures
            try:
                results = retry_sync_operation(
                    multicall.call,
                    block_number,
                    max_attempts=RPC_RETRY_CONFIG.max_attempts,
                    base_delay=RPC_RETRY_CONFIG.base_delay,
                    max_delay=RPC_RETRY_CONFIG.max_delay,
                    operation_name="eligibility_multicall",
                )
            except Exception as e:
                # If multicall fails (e.g., one call reverts), fall back to smaller batches
                # This can happen with Pendle if a user no longer has a position
                if len(unique_users) > 1:
                    # Split into smaller batches and retry
                    batch_size = max(1, len(unique_users) // 4)  # Try 4 batches
                    all_results = []

                    for batch_start in range(0, len(unique_users), batch_size):
                        batch_users = unique_users[batch_start:batch_start + batch_size]
                        batch_multicall = W3Multicall(w3)

                        # Rebuild calls for this batch
                        for user in batch_users:
                            if protocol == "pendle":
                                batch_multicall.add(
                                    W3Multicall.Call(
                                        gauge_controller_address,
                                        "getUserPoolVote(address,address)(uint256,uint256,uint256)",
                                        [
                                            to_checksum_address(user),
                                            to_checksum_address(gauge_address),
                                        ],
                                    )
                                )
                                ve_address = registry.get_ve_address(protocol)
                                if ve_address:
                                    batch_multicall.add(
                                        W3Multicall.Call(
                                            to_checksum_address(ve_address),
                                            "positionData(address)(uint128,uint128)",
                                            [to_checksum_address(user)],
                                        )
                                    )
                            elif protocol == "yb":
                                batch_multicall.add(
                                    W3Multicall.Call(
                                        gauge_controller_address,
                                        "last_user_vote(address,address)(uint256)",
                                        [
                                            to_checksum_address(user),
                                            to_checksum_address(gauge_address),
                                        ],
                                    )
                                )
                                batch_multicall.add(
                                    W3Multicall.Call(
                                        gauge_controller_address,
                                        "vote_user_slopes(address,address)(uint256,uint256,uint256,uint256)",
                                        [
                                            to_checksum_address(user),
                                            to_checksum_address(gauge_address),
                                        ],
                                    )
                                )
                            else:
                                batch_multicall.add(
                                    W3Multicall.Call(
                                        gauge_controller_address,
                                        "last_user_vote(address,address)(uint256)",
                                        [
                                            to_checksum_address(user),
                                            to_checksum_address(gauge_address),
                                        ],
                                    )
                                )
                                batch_multicall.add(
                                    W3Multicall.Call(
                                        gauge_controller_address,
                                        "vote_user_slopes(address,address)(int128,int128,uint256)",
                                        [
                                            to_checksum_address(user),
                                            to_checksum_address(gauge_address),
                                        ],
                                    )
                                )

                        try:
                            batch_results = retry_sync_operation(
                                batch_multicall.call,
                                block_number,
                                max_attempts=RPC_RETRY_CONFIG.max_attempts,
                                base_delay=RPC_RETRY_CONFIG.base_delay,
                                max_delay=RPC_RETRY_CONFIG.max_delay,
                                operation_name=f"eligibility_batch_{batch_start}",
                            )
                            all_results.extend(batch_results)
                        except Exception as batch_err:
                            _logger.debug(
                                "Batch multicall failed for batch %d: %s",
                                batch_start,
                                batch_err,
                            )
                            # If even a small batch fails after retries, use placeholder results
                            for user in batch_users:
                                # Add placeholder results (will be filtered out later)
                                if protocol == "pendle":
                                    all_results.extend([(0, 0, 0), (0, 0)])
                                elif protocol == "yb":
                                    all_results.extend([0, (0, 0, 0, 0)])
                                else:
                                    all_results.extend([0, (0, 0, 0)])

                    results = all_results
                else:
                    # Single user failed, re-raise
                    raise

            eligible_users: List[EligibleUser] = []

            # Step 4: Filter to only ELIGIBLE users based on vote status
            for i in range(0, len(results), 2):
                user = unique_users[i // 2]

                # Initialize variables
                last_vote, slope, power, end, bias = 0, 0, 0, 0, 0

                if protocol == "pendle":
                    # Pendle data structure
                    last_vote = 0  # Pendle doesn't track last vote timestamp
                    power, _, slope = results[i]
                    end = results[i + 1][1]  # Position end timestamp
                elif protocol == "yb":
                    # YB data structure: last_vote + (slope, bias, power, end)
                    last_vote = results[i]
                    slope, bias, power, end = results[i + 1]
                else:
                    # Standard gauge controller data
                    last_vote = results[i]
                    slope, power, end = results[i + 1]

                # Basic eligibility check (fail-fast)
                # Lock must NOT have ended AND user must have voted before current epoch
                if not (current_epoch < end and current_epoch > last_vote):
                    continue

                # Protocol-specific eligibility and slope logic
                is_eligible = False
                final_slope = slope

                if protocol == "yb":
                    # Special case for YB: Infinite lock (perma lock)
                    if end == MAX_UINT256:
                        if bias > 0:
                            is_eligible = True
                            final_slope = bias  # Use bias as effective slope for infinite lock
                    # Normal YB case: Finite lock
                    elif slope > 0:
                        is_eligible = True
                # All other protocols: Check if slope is positive
                elif slope > 0:
                    is_eligible = True

                if is_eligible:
                    eligible_users.append(
                        EligibleUser(
                            user=user,
                            last_vote=last_vote,
                            slope=final_slope,
                            power=power,
                            end=end,
                        )
                    )

            return Result.ok(eligible_users)
        except Exception as e:
            return Result.fail(
                ProcessingError(
                    source="eligibility_service",
                    message=f"Error getting eligible users: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    context=context,
                    exception=e,
                )
            )
