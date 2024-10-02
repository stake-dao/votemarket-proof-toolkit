"""This module provides functionality for generating and managing proofs for VoteMarket."""

import os
from proofs.proof_generator.user_proof import generate_user_proof
from proofs.proof_generator.gauge_proof import generate_gauge_proof
from proofs.block_header.encoder import get_block_info
from shared.web3_service import Web3Service
from shared.exceptions import VoteMarketProofsException
from shared.types import UserProof, GaugeProof, BlockInfo

class VoteMarketProofs:
    """A global class for generating and managing proofs"""

    def __init__(self, chain_id: int):
        rpc_url = os.getenv("ETHEREUM_MAINNET_RPC_URL")

        print("Used rpc url: ", rpc_url)
        if not rpc_url:
            raise ValueError("ETHEREUM_MAINNET_RPC_URL environment variable is not set")
        self.web3_service = Web3Service(chain_id, rpc_url)

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
            return UserProof(account_proof=account_proof, storage_proof=storage_proof)
        except Exception:
            raise VoteMarketProofsException("Error generating user proof")

    def get_gauge_proof(
        self, protocol: str, gauge_address: str, CURRENT_EPOCH: int, block_number: int
    ) -> GaugeProof:
        """Generate a gauge proof for a given protocol, gauge, current epoch, and block number"""
        try:
            gauge_controller_proof, point_data_proof = generate_gauge_proof(
                self.web3_service.get_w3(),
                protocol,
                gauge_address,
                CURRENT_EPOCH,
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
            block_info = get_block_info(self.web3_service.get_w3(), block_number)
            return BlockInfo(
                BlockNumber=block_info["BlockNumber"],
                BlockHash=block_info["BlockHash"],
                BlockTimestamp=block_info["BlockTimestamp"],
                RlpBlockHeader=block_info["RlpBlockHeader"],
            )
        except Exception:
            raise VoteMarketProofsException("Error getting block info")
