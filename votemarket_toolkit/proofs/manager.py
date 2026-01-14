from typing import Optional

from eth_utils import to_checksum_address

from votemarket_toolkit.proofs.generators.block_info import get_block_info
from votemarket_toolkit.proofs.generators.gauge_proof import (
    generate_gauge_proof,
)
from votemarket_toolkit.proofs.generators.user_proof import generate_user_proof
from votemarket_toolkit.proofs.types import BlockInfo, GaugeProof, UserProof
from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.constants import GlobalConstants
from votemarket_toolkit.shared.logging import get_logger
from votemarket_toolkit.shared.results import (
    ErrorSeverity,
    ProcessingError,
    Result,
)
from votemarket_toolkit.shared.retry import retry_sync_operation
from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.utils import get_rounded_epoch

_logger = get_logger(__name__)


class GaugeValidationResult:
    """Result of gauge validation with reason."""

    def __init__(
        self,
        is_valid: bool,
        reason: Optional[str] = None,
        protocol: Optional[str] = None,
        gauge: Optional[str] = None,
    ):
        self.is_valid = is_valid
        self.reason = reason
        self.protocol = protocol
        self.gauge = gauge


class VoteMarketProofs:
    """A global class for generating and managing proofs"""

    def __init__(self, chain_id: int):
        rpc_url = GlobalConstants.get_rpc_url(chain_id)

        self.chain_id = chain_id
        self.yb_gauges = None
        if not rpc_url:
            raise ValueError(
                f"RPC URL environment variable for {chain_id} is not set"
            )
        self.web3_service = Web3Service(chain_id, rpc_url)

    def get_gauge_proof(
        self,
        protocol: str,
        gauge_address: str,
        current_epoch: int,
        block_number: int,
        max_retries: int = 3,
    ) -> Result[GaugeProof]:
        """
        Generate a gauge proof for a given protocol, gauge, current epoch, and block number.

        Args:
            protocol: The protocol name
            gauge_address: The gauge address
            current_epoch: The epoch timestamp
            block_number: The block number
            max_retries: Number of retries for RPC calls

        Returns:
            Result[GaugeProof]: Success with proof data, or failure with error
        """
        current_epoch = get_rounded_epoch(current_epoch)
        context = {
            "protocol": protocol,
            "gauge": gauge_address,
            "epoch": current_epoch,
            "block": block_number,
        }

        try:

            def _generate():
                return generate_gauge_proof(
                    self.web3_service.w3,
                    protocol,
                    gauge_address,
                    current_epoch,
                    block_number,
                )

            gauge_controller_proof, point_data_proof = retry_sync_operation(
                _generate,
                max_attempts=max_retries,
                base_delay=1.0,
                operation_name=f"gauge_proof_{gauge_address[:10]}",
            )

            return Result.ok(
                GaugeProof(
                    gauge_controller_proof=gauge_controller_proof,
                    point_data_proof=point_data_proof,
                )
            )
        except Exception as e:
            return Result.fail(
                ProcessingError(
                    source="gauge_proof",
                    message=f"Error generating gauge proof: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    context=context,
                    exception=e,
                )
            )

    def get_user_proof(
        self,
        protocol: str,
        gauge_address: str,
        user: str,
        block_number: int,
        max_retries: int = 3,
    ) -> Result[UserProof]:
        """
        Generate a user proof for a given protocol, gauge, user, and block number.

        Args:
            protocol: The protocol name
            gauge_address: The gauge address
            user: The user address
            block_number: The block number
            max_retries: Number of retries for RPC calls

        Returns:
            Result[UserProof]: Success with proof data, or failure with error
        """
        context = {
            "protocol": protocol,
            "gauge": gauge_address,
            "user": user,
            "block": block_number,
        }

        try:

            def _generate():
                return generate_user_proof(
                    self.web3_service.w3,
                    protocol,
                    gauge_address,
                    user,
                    block_number,
                )

            account_proof, storage_proof = retry_sync_operation(
                _generate,
                max_attempts=max_retries,
                base_delay=1.0,
                operation_name=f"user_proof_{user[:10]}",
            )

            return Result.ok(
                UserProof(
                    account_proof=account_proof, storage_proof=storage_proof
                )
            )
        except Exception as e:
            return Result.fail(
                ProcessingError(
                    source="user_proof",
                    message=f"Error generating user proof: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    context=context,
                    exception=e,
                )
            )

    def get_block_info(
        self, block_number: int, max_retries: int = 3
    ) -> Result[BlockInfo]:
        """
        Get block info for a given block number.

        Args:
            block_number: The block number
            max_retries: Number of retries for RPC calls

        Returns:
            Result[BlockInfo]: Success with block info, or failure with error
        """
        try:

            def _get_info():
                return get_block_info(self.web3_service.w3, block_number)

            block_info = retry_sync_operation(
                _get_info,
                max_attempts=max_retries,
                base_delay=1.0,
                operation_name=f"block_info_{block_number}",
            )

            return Result.ok(
                BlockInfo(
                    block_number=block_info["block_number"],
                    block_hash=block_info["block_hash"],
                    block_timestamp=block_info["block_timestamp"],
                    rlp_block_header=block_info["rlp_block_header"],
                )
            )
        except Exception as e:
            return Result.fail(
                ProcessingError(
                    source="block_info",
                    message=f"Error getting block info: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    context={"block_number": block_number},
                    exception=e,
                )
            )

    def is_valid_gauge(
        self, protocol: str, gauge: str, max_retries: int = 3
    ) -> Result[GaugeValidationResult]:
        """
        Validate a gauge with detailed error information and retry logic.

        Args:
            protocol: The protocol name
            gauge: The gauge address
            max_retries: Number of retry attempts for RPC calls

        Returns:
            Result[GaugeValidationResult]: Success with validation result, or failure with error
        """
        # Get gauge controller address
        gauge_controller_address = registry.get_gauge_controller(protocol)
        if not gauge_controller_address:
            return Result.ok(
                GaugeValidationResult(
                    is_valid=False,
                    reason=f"No gauge controller found for protocol: {protocol}",
                    protocol=protocol,
                    gauge=gauge,
                )
            )

        def _do_validation() -> Result[GaugeValidationResult]:
            if protocol == "pendle":
                try:
                    gauge_controller_contract = self.web3_service.get_contract(
                        gauge_controller_address, "pendle_gauge_controller"
                    )
                    active_pools = (
                        gauge_controller_contract.functions.getAllActivePools().call()
                    )

                    for active_pool in active_pools:
                        if active_pool.lower() == gauge.lower():
                            return Result.ok(
                                GaugeValidationResult(
                                    is_valid=True,
                                    reason="Gauge found in active pools",
                                    protocol=protocol,
                                    gauge=gauge,
                                )
                            )
                    return Result.ok(
                        GaugeValidationResult(
                            is_valid=False,
                            reason="Gauge not found in Pendle active pools",
                            protocol=protocol,
                            gauge=gauge,
                        )
                    )
                except Exception as e:
                    # If getAllActivePools() fails, assume valid with warning
                    result = Result.ok(
                        GaugeValidationResult(
                            is_valid=True,
                            reason=f"getAllActivePools() failed, assuming valid: {str(e)}",
                            protocol=protocol,
                            gauge=gauge,
                        )
                    )
                    result.add_warning(
                        source="gauge_validation",
                        message=f"Could not verify Pendle gauge via getAllActivePools(): {str(e)}",
                        context={"protocol": protocol, "gauge": gauge},
                    )
                    return result

            elif protocol == "yb":
                if self.yb_gauges is None:
                    self.yb_gauges = {}
                    gauge_controller_contract = self.web3_service.get_contract(
                        gauge_controller_address, "yb_gauge_controller"
                    )
                    nb_gauges = (
                        gauge_controller_contract.functions.n_gauges().call()
                    )
                    for i in range(nb_gauges):
                        gauge_address = (
                            gauge_controller_contract.functions.gauges(i).call()
                        )
                        self.yb_gauges[gauge_address.lower()] = True

                is_valid = gauge.lower() in self.yb_gauges
                return Result.ok(
                    GaugeValidationResult(
                        is_valid=is_valid,
                        reason="Gauge found in YB gauges list"
                        if is_valid
                        else "Gauge not found in YB gauges list",
                        protocol=protocol,
                        gauge=gauge,
                    )
                )
            else:
                gauge_controller_contract = self.web3_service.get_contract(
                    gauge_controller_address, "gauge_controller"
                )
                gauge_controller_contract.functions.gauge_types(
                    to_checksum_address(gauge)
                ).call()
                return Result.ok(
                    GaugeValidationResult(
                        is_valid=True,
                        reason="gauge_types() call succeeded",
                        protocol=protocol,
                        gauge=gauge,
                    )
                )

        try:
            return retry_sync_operation(
                _do_validation,
                max_attempts=max_retries,
                base_delay=1.0,
                operation_name=f"validate_gauge_{gauge[:10]}",
            )
        except Exception as e:
            return Result.fail(
                ProcessingError(
                    source="gauge_validation",
                    message=f"Gauge validation failed: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    context={"protocol": protocol, "gauge": gauge},
                    exception=e,
                )
            )
