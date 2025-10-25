from eth_utils import to_checksum_address

from votemarket_toolkit.proofs.generators.block_info import get_block_info
from votemarket_toolkit.proofs.generators.gauge_proof import (
    generate_gauge_proof,
)
from votemarket_toolkit.proofs.generators.user_proof import generate_user_proof
from votemarket_toolkit.proofs.types import BlockInfo, GaugeProof, UserProof
from votemarket_toolkit.shared.constants import (
    GaugeVotesConstants,
    GlobalConstants,
)
from votemarket_toolkit.shared.exceptions import VoteMarketProofsException
from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.utils import get_rounded_epoch


class VoteMarketProofs:
    """A global class for generating and managing proofs"""

    def __init__(self, chain_id: int):
        rpc_url = GlobalConstants.get_rpc_url(chain_id)

        self.chain_id = chain_id
        self.yb_gauges = None
        if not rpc_url:
            raise ValueError(
                "ETHEREUM_MAINNET_RPC_URL environment variable is not set"
            )
        self.web3_service = Web3Service(chain_id, rpc_url)

    def get_gauge_proof(
        self,
        protocol: str,
        gauge_address: str,
        current_epoch: int,
        block_number: int,
    ) -> GaugeProof:
        """Generate a gauge proof for a given protocol, gauge, current epoch, and block number"""

        # We always treat the epoch rounded to the day
        current_epoch = get_rounded_epoch(current_epoch)

        try:
            gauge_controller_proof, point_data_proof = generate_gauge_proof(
                self.web3_service.w3,
                protocol,
                gauge_address,
                current_epoch,
                block_number,
            )

            return GaugeProof(
                gauge_controller_proof=gauge_controller_proof,
                point_data_proof=point_data_proof,
            )
        except Exception as e:
            raise VoteMarketProofsException(
                f"Error generating gauge proof: {str(e)}"
            )

    def get_user_proof(
        self,
        protocol: str,
        gauge_address: str,
        user: str,
        block_number: int,
    ) -> UserProof:
        """
        Generate a user proof for a given protocol, gauge, user, and block number.

        Args:
            protocol (str): The protocol name.
            gauge_address (str): The gauge address.
            user (str): The user address.
            block_number (int): The block number to use.

        Returns:
            UserProof: The generated user proof.

        Raises:
            VoteMarketProofsException: If there's an error generating the user proof.
        """
        try:
            account_proof, storage_proof = generate_user_proof(
                self.web3_service.w3,
                protocol,
                gauge_address,
                user,
                block_number,
            )
            return UserProof(
                account_proof=account_proof, storage_proof=storage_proof
            )
        except Exception:
            raise VoteMarketProofsException("Error generating user proof")

    def get_block_info(self, block_number: int) -> BlockInfo:
        """Get block info for a given block number"""
        try:
            block_info = get_block_info(self.web3_service.w3, block_number)
            return BlockInfo(
                block_number=block_info["block_number"],
                block_hash=block_info["block_hash"],
                block_timestamp=block_info["block_timestamp"],
                rlp_block_header=block_info["rlp_block_header"],
            )
        except Exception:
            raise VoteMarketProofsException("Error getting block info")

    def is_valid_gauge(self, protocol: str, gauge: str) -> bool:
        """
        Check if a gauge is valid for a given protocol.

        Args:
            protocol (str): The protocol name.
            gauge (str): The gauge address.

        Returns:
        bool: True if the gauge is valid, False otherwise.
        """

        # Get gauge controller address
        gauge_controller_address = GaugeVotesConstants.GAUGE_CONTROLLER[
            protocol
        ]

        try:
            if protocol == "pendle":
                gauge_controller_contract = self.web3_service.get_contract(
                    gauge_controller_address, "pendle_gauge_controller"
                )
                active_pools = gauge_controller_contract.functions.getAllActivePools().call()

                for active_pool in active_pools:
                    if active_pool.lower() == gauge.lower():
                        return True
                return False
            if protocol == "yb":
                if self.yb_gauges == None:
                    self.yb_gauges = {}
                    gauge_controller_contract = self.web3_service.get_contract(
                        gauge_controller_address, "yb_gauge_controller"
                    )
                    nb_gauges = gauge_controller_contract.functions.n_gauges().call()

                    for i in range(nb_gauges):
                        gauge_address = gauge_controller_contract.functions.gauges(i).call()
                        self.yb_gauges[gauge_address.lower()] = True
                return gauge.lower() in self.yb_gauges
            else:
                gauge_controller_contract = self.web3_service.get_contract(
                    gauge_controller_address, "gauge_controller"
                )
                gauge_controller_contract.functions.gauge_types(
                    to_checksum_address(gauge)
                ).call()
                return True
        except Exception:
            return False
