"""
Oracle service for querying canonical block numbers from VoteMarket oracle.

This service interfaces with the VoteMarket oracle contracts to get
verified block numbers for specific epochs, ensuring all participants
use the same block for merkle tree consistency.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from eth_utils import to_checksum_address
from w3multicall.multicall import W3Multicall

from votemarket_toolkit.shared.logging import get_logger
from votemarket_toolkit.shared.results import (
    ErrorSeverity,
    ProcessingError,
    Result,
)
from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.utils.blockchain import get_rounded_epoch

_logger = get_logger(__name__)


class OracleStatus(Enum):
    """Status of oracle configuration."""

    CONFIGURED = "configured"
    NOT_SET = "not_set"
    BLOCK_NOT_SET = "block_not_set"


@dataclass
class EpochBlockResult:
    """Result of querying epoch block number."""

    epoch: int
    block_number: int
    status: OracleStatus
    error: Optional[str] = None


class OracleService:
    """
    Service for querying VoteMarket oracle data.

    The oracle stores canonical block numbers for each epoch to ensure
    all participants generate consistent merkle trees.
    """

    def __init__(self, chain_id: int):
        """
        Initialize the oracle service.

        Args:
            chain_id: Blockchain network ID (1 for Ethereum, 42161 for Arbitrum)
        """
        self.chain_id = chain_id
        self.web3_service = Web3Service.get_instance(chain_id)

    def get_epochs_block_with_status(
        self, chain_id: int, platform: str, epochs: List[int]
    ) -> Result[Dict[int, EpochBlockResult]]:
        """
        Get oracle-verified block numbers with explicit status for each epoch.

        This method provides detailed status information that allows callers
        to distinguish between "oracle not configured", "block not set yet",
        and "block successfully retrieved".

        Args:
            chain_id: Blockchain network ID
            platform: VoteMarket platform contract address
            epochs: List of epoch timestamps to query

        Returns:
            Result[Dict[int, EpochBlockResult]]: Detailed results with status
        """
        epochs = [get_rounded_epoch(epoch) for epoch in epochs]
        context = {"chain_id": chain_id, "platform": platform, "epochs": epochs}

        try:
            w3 = self.web3_service.w3
            multicall = W3Multicall(w3)

            # Navigate the oracle hierarchy
            platform_contract = self.web3_service.get_contract(
                platform, "vm_platform"
            )
            lens = platform_contract.functions.ORACLE().call()
            lens_address = to_checksum_address(lens.lower())

            lens_contract = self.web3_service.get_contract(
                lens_address, "oracle_lens"
            )
            oracle_address = lens_contract.functions.oracle().call()
            oracle_address = to_checksum_address(oracle_address.lower())

            # EXPLICIT ERROR: Oracle not configured
            if oracle_address == "0x0000000000000000000000000000000000000000":
                _logger.warning(
                    "Oracle not configured for platform %s on chain %d",
                    platform,
                    chain_id,
                )
                results = {
                    epoch: EpochBlockResult(
                        epoch=epoch,
                        block_number=0,
                        status=OracleStatus.NOT_SET,
                        error="Oracle contract not configured for platform",
                    )
                    for epoch in epochs
                }
                return Result.degraded_result(
                    results,
                    reason=f"Oracle not configured for platform {platform}",
                )

            # Build multicall queries
            for epoch in epochs:
                multicall.add(
                    W3Multicall.Call(
                        oracle_address,
                        "epochBlockNumber(uint256)(bytes32,bytes32,uint256,uint256)",
                        [epoch],
                    )
                )

            raw_results = multicall.call()

            # Build typed results with explicit status
            results: Dict[int, EpochBlockResult] = {}
            for i, epoch in enumerate(epochs):
                block_num = raw_results[i][2] if raw_results[i][2] != 0 else 0
                if block_num > 0:
                    results[epoch] = EpochBlockResult(
                        epoch=epoch,
                        block_number=block_num,
                        status=OracleStatus.CONFIGURED,
                    )
                else:
                    results[epoch] = EpochBlockResult(
                        epoch=epoch,
                        block_number=0,
                        status=OracleStatus.BLOCK_NOT_SET,
                        error="Block not yet set for this epoch",
                    )

            return Result.ok(results)

        except Exception as e:
            _logger.error(
                "Oracle query failed for platform %s: %s",
                platform,
                str(e),
            )
            return Result.fail(
                ProcessingError(
                    source="oracle_service",
                    message=f"Failed to query oracle: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    context=context,
                    exception=e,
                )
            )

    def get_epochs_block(
        self, chain_id: int, platform: str, epochs: List[int]
    ) -> Dict[int, int]:
        """
        Get oracle-verified block numbers for specific epochs.

        The VoteMarket oracle stores the "canonical" block number for each epoch.
        All participants must use the same block to ensure merkle tree consistency.

        Returns 0 for epochs where the oracle hasn't been updated yet.

        NOTE: This method logs warnings for degraded/failed results but returns
        a simple dict for backwards compatibility. Use get_epochs_block_with_status()
        for explicit error handling.

        Args:
            chain_id: Blockchain network ID (1=Ethereum, 42161=Arbitrum)
            platform: VoteMarket platform contract address
            epochs: List of epoch timestamps to query

        Returns:
            Dict[int, int]: Mapping of epoch → block number
                           (0 means oracle not updated for that epoch)
        """
        result = self.get_epochs_block_with_status(chain_id, platform, epochs)

        if not result.success:
            _logger.error(
                "Oracle query failed: %s",
                result.errors[0].message if result.errors else "Unknown",
            )
            return {epoch: 0 for epoch in epochs}

        if result.degraded:
            _logger.warning(
                "Oracle query degraded: %s",
                result.errors[0].message if result.errors else "Unknown",
            )

        # Convert to simple dict
        return {epoch: data.block_number for epoch, data in result.data.items()}
