"""
A global class for generating and managing proofs for VoteMarket.

This class provides methods to generate user proofs, gauge proofs, and retrieve block information.
It initializes with a Web3 service for the specified chain ID.
"""

from proofs.proof_generator.user_proof import generate_user_proof
from proofs.proof_generator.gauge_proof import generate_gauge_proof
from proofs.block_header.encoder import get_block_info
from shared.constants import GaugeVotesConstants, GlobalConstants
from shared.utils import get_rounded_epoch
from shared.web3_service import Web3Service
from shared.exceptions import VoteMarketProofsException
from shared.types import UserProof, GaugeProof, BlockInfo
from eth_utils import to_checksum_address


class VoteMarketProofs:
    """A global class for generating and managing proofs"""

    def __init__(self, chain_id: int):
        rpc_url = GlobalConstants.CHAIN_ID_TO_RPC[chain_id]

        self.chain_id = chain_id
        if not rpc_url:
            raise ValueError(
                "ETHEREUM_MAINNET_RPC_URL environment variable is not set"
            )
        self.web3_service = Web3Service(chain_id, rpc_url)

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
        gauge_controller_contract = self.web3_service.get_contract(
            gauge_controller_address, "gauge_controller", self.chain_id
        )

        try:
            gauge_controller_contract.functions.gauge_types(
                to_checksum_address(gauge)
            ).call()
            return True
        except Exception:
            return False

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
                self.web3_service.get_w3(),
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
                self.web3_service.get_w3(),
                protocol,
                gauge_address,
                current_epoch,
                block_number,
            )
            return GaugeProof(
                gauge_controller_proof=gauge_controller_proof,
                point_data_proof=point_data_proof,
            )
        except Exception:
            raise VoteMarketProofsException("Error generating gauge proof")

    def get_block_info(self, block_number: int) -> BlockInfo:
        """Get block info for a given block number"""
        try:
            block_info = get_block_info(
                self.web3_service.get_w3(), block_number
            )
            return BlockInfo(
                block_number=block_info["block_number"],
                block_hash=block_info["block_hash"],
                block_timestamp=block_info["block_timestamp"],
                rlp_block_header=block_info["rlp_block_header"],
            )
        except Exception:
            raise VoteMarketProofsException("Error getting block info")
