from typing import Any, Dict, Tuple
from proofs.proof_generator.user_proof import generate_user_proof
from proofs.proof_generator.gauge_proof import generate_gauge_proof
from proofs.block_header.encoder import get_block_info
from shared.web3_service import Web3Service
from shared.exceptions import VoteMarketProofsException


class VoteMarketProofs:
    def __init__(self, rpc_url: str):
        self.web3_service = Web3Service(rpc_url)

    def get_user_proof(
        self,
        protocol: str,
        gauge_address: str,
        user: str,
        block_number: int,
    ) -> Tuple[bytes, bytes]:
        try:
            return generate_user_proof(
                self.web3_service.w3,
                protocol,
                gauge_address,
                user,
                block_number,
            )
        except Exception as e:
            raise VoteMarketProofsException(f"Error generating user proof: {str(e)}")

    def get_gauge_proof(
        self, protocol: str, gauge_address: str, current_period: int, block_number: int
    ) -> Tuple[bytes, bytes]:
        try:
            return generate_gauge_proof(
                self.web3_service.w3,
                protocol,
                gauge_address,
                current_period,
                block_number,
            )
        except Exception as e:
            raise VoteMarketProofsException(f"Error generating gauge proof: {str(e)}")

    def get_block_info(self, block_number: int) -> Dict[str, Any]:
        try:
            return get_block_info(self.web3_service.w3, block_number)
        except Exception as e:
            raise VoteMarketProofsException(f"Error getting block info: {str(e)}")
