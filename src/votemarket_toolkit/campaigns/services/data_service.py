"""
VoteMarketDataService - Fetches eligible voters and oracle blocks

This service provides blockchain data needed by external scripts to coordinate
proof generation. It identifies WHO is eligible and WHEN (which block) to use.

NOTE: This service is currently in campaigns/services/ but is actually used by:
- External scripts (vm_active_proofs.py) for proof generation coordination
- Commands (get_epoch_blocks.py) for oracle queries

TODO: Consider moving to shared/services/ or proofs/services/ for better organization

Main Functions:
1. get_eligible_users() - Identifies voters who can claim rewards
2. get_epochs_block() - Gets canonical block numbers from oracle

Supported Protocols:
- Curve/Balancer/Frax: Standard gauge controller interface
- Pendle: Custom voting interface with different data structure
"""

from typing import Dict, List, Optional

from eth_utils import to_checksum_address
from w3multicall.multicall import W3Multicall

from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.exceptions import VoteMarketDataException
from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.shared.types import EligibleUser
from votemarket_toolkit.utils.blockchain import get_rounded_epoch
from votemarket_toolkit.votes.services.votes_service import votes_service


class VoteMarketDataService:
    """
    Fetches voter eligibility and oracle block data from blockchain.

    Used by external scripts to determine:
    - WHO: Which users are eligible to claim (get_eligible_users)
    - WHEN: What block number to use for proofs (get_epochs_block)

    This service does NOT generate proofs - it provides data that external
    scripts use to coordinate the actual proof generation process.

    Current users:
    - vm_active_proofs.py: Uses this to get eligible users
    - get_epoch_blocks.py: Command line tool for oracle queries

    Attributes:
        chain_id: The blockchain network ID
        web3_service: Web3 service instance for blockchain interactions
    """

    def __init__(self, chain_id: int):
        """
        Initialize the data service for a specific blockchain.

        Args:
            chain_id: Blockchain network ID (1 for Ethereum, 42161 for Arbitrum)
        """
        self.chain_id = chain_id
        self.web3_service = Web3Service.get_instance(chain_id)

    def get_web3_service_for_chain(self, chain_id: int) -> Web3Service:
        """
        Get Web3Service instance for a specific chain.

        Args:
            chain_id: Target blockchain network ID

        Returns:
            Web3Service: Configured service instance for the chain
        """
        return Web3Service.get_instance(chain_id)

    async def get_eligible_users(
        self,
        protocol: str,
        gauge_address: str,
        current_epoch: int,
        block_number: int,
        chain_id: Optional[int] = None,
        platform: Optional[str] = None,
    ) -> List[EligibleUser]:
        """
        Identify users who are eligible to claim rewards for a gauge/epoch.

        Returns users who meet ALL eligibility criteria:
        1. User voted for the gauge before the epoch (last_vote < current_epoch)
        2. Vote is still active at the epoch (end > current_epoch)
        3. User has positive voting power (slope > 0)

        External scripts use this to determine which users need proofs generated.
        This method itself does NOT generate or interact with proofs.

        Args:
            protocol: Protocol name ("curve", "balancer", "frax", "pendle")
            gauge_address: Address of the gauge to check
            current_epoch: Timestamp of the epoch to check eligibility for
            block_number: Block number to query at (or fetch from oracle)
            chain_id: Optional - if provided with platform, fetches canonical block from oracle
            platform: Optional - VoteMarket platform address for oracle lookup

        Returns:
            List[EligibleUser]: Users who CAN claim (need proofs generated):
                - user: User address
                - last_vote: When they last voted (0 for Pendle)
                - slope: Voting power decrease rate
                - power: Current voting power amount
                - end: When their vote expires

        Raises:
            VoteMarketDataException: If blockchain data retrieval fails

        Example:
            >>> # Get list of users who need proofs
            >>> eligible = await service.get_eligible_users(
            ...     protocol="curve",
            ...     gauge_address="0x7E1444BA99dcdFfE8fBdb42C02fb0DA4",
            ...     current_epoch=1699920000,
            ...     block_number=18500000
            ... )
            >>> print(f"Need to generate proofs for {len(eligible)} users")
        """
        # Always round epoch to the day for consistency
        current_epoch = get_rounded_epoch(current_epoch)

        try:
            w3 = self.web3_service.w3

            # If chain and platform provided, fetch the canonical block number from oracle
            if chain_id is not None and platform is not None:
                epoch_blocks = self.get_epochs_block(
                    chain_id, platform, [current_epoch]
                )
                block_number = epoch_blocks[current_epoch]
                if block_number == 0:
                    raise VoteMarketDataException(
                        f"No block set for epoch {current_epoch}"
                    )

            # Initialize multicall for efficient batch queries
            multicall = W3Multicall(w3)

            # Get the gauge controller contract address for this protocol
            gauge_controller = registry.get_gauge_controller(protocol)
            if not gauge_controller:
                raise VoteMarketDataException(
                    f"No gauge controller found for protocol: {protocol}"
                )
            gauge_controller_address = to_checksum_address(gauge_controller)

            # Step 1: Get all users who have EVER voted on this gauge
            # This uses the votes indexing service which has historical vote data
            gauge_votes = await votes_service.get_gauge_votes(
                protocol, gauge_address, block_number
            )
            unique_users = list(set(vote.user for vote in gauge_votes.votes))

            # Step 2: Query current vote status for each historical voter
            # We need to check if their vote is still active at the target epoch
            for user in unique_users:
                if protocol == "pendle":
                    # Pendle uses different contract interface
                    # getUserPoolVote returns (power, timestamp, weight)
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
            results = multicall.call(block_number)

            eligible_users: List[EligibleUser] = []

            # Step 4: Filter to only ELIGIBLE users based on vote status
            # Process results in pairs (2 calls per user)
            for i in range(0, len(results), 2):
                user = unique_users[i // 2]

                if protocol == "pendle":
                    # Pendle data structure: getUserPoolVote returns (power, timestamp, weight)
                    last_vote = 0  # Pendle doesn't track last vote timestamp separately
                    power, _, slope = results[i]
                    # Position data returns (amount, end_timestamp)
                    end = results[i + 1][1]
                else:
                    # Standard gauge controller data (Curve/Balancer/Frax)
                    last_vote = results[i]  # Timestamp of last vote
                    slope, power, end = results[i + 1]  # Vote slope data

                # Eligibility check - user CAN claim rewards if:
                # 1. Vote hasn't expired yet (current_epoch < end)
                # 2. User voted before this epoch (current_epoch > last_vote)
                # 3. User has positive voting power (slope > 0)
                if (
                    current_epoch < end
                    and current_epoch > last_vote
                    and slope > 0
                ):
                    eligible_users.append(
                        EligibleUser(
                            user=user,
                            last_vote=last_vote,
                            slope=slope,
                            power=power,
                            end=end,
                        )
                    )

            return eligible_users
        except Exception as e:
            raise VoteMarketDataException(
                f"Error getting eligible users: {str(e)}"
            )

    def get_epochs_block(
        self, chain_id: int, platform: str, epochs: List[int]
    ) -> Dict[int, int]:
        """
        Get oracle-verified block numbers for specific epochs.

        The VoteMarket oracle stores the "canonical" block number for each epoch.
        All participants must use the same block to ensure merkle tree consistency.

        Returns 0 for epochs where the oracle hasn't been updated yet.

        Args:
            chain_id: Blockchain network ID (1=Ethereum, 42161=Arbitrum)
            platform: VoteMarket platform contract address
            epochs: List of epoch timestamps to query

        Returns:
            Dict[int, int]: Mapping of epoch → block number
                           (0 means oracle not updated for that epoch)

        Example:
            >>> # Get canonical blocks for proof generation
            >>> blocks = service.get_epochs_block(
            ...     chain_id=1,
            ...     platform="0x0000000895cB182E6f983eb4D8b4E0Aa0B31Ae4c",
            ...     epochs=[1699920000, 1700524800]
            ... )
            >>> # Use these blocks for consistent proof generation
            >>> for epoch, block in blocks.items():
            ...     if block > 0:
            ...         # Generate proofs using this canonical block
            ...         proof = proof_manager.get_user_proof(..., block_number=block)
        """
        # Always round epochs to the day for consistency
        epochs = [get_rounded_epoch(epoch) for epoch in epochs]

        w3 = self.web3_service.w3
        multicall = W3Multicall(w3)

        # Navigate the oracle hierarchy: Platform → Lens → Oracle
        platform_contract = self.web3_service.get_contract(
            platform, "vm_platform"
        )

        # Get oracle lens address from platform
        lens = platform_contract.functions.ORACLE().call()
        lens_address = to_checksum_address(lens.lower())

        # Get actual oracle address from lens (the lens is a proxy)
        lens_contract = self.web3_service.get_contract(
            lens_address, "oracle_lens"
        )
        oracle_address = lens_contract.functions.oracle().call()
        oracle_address = to_checksum_address(oracle_address.lower())

        # If no oracle is set, return zeros for all epochs
        if oracle_address == "0x0000000000000000000000000000000000000000":
            return {epoch: 0 for epoch in epochs}

        # Build multicall queries for each epoch
        for epoch in epochs:
            multicall.add(
                W3Multicall.Call(
                    oracle_address,
                    "epochBlockNumber(uint256)(bytes32,bytes32,uint256,uint256)",
                    [epoch],
                )
            )

        # Execute all queries in a single call
        results = multicall.call()

        # Map epochs to their block numbers
        # epochBlockNumber returns (merkleRoot, ipfsHash, blockNumber, timestamp)
        # We extract blockNumber (index 2) from the result
        return {
            epochs[i]: results[i][2] if results[i][2] != 0 else 0
            for i in range(len(epochs))
        }
