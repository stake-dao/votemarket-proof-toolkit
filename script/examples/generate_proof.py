""" Example of how to generate proofs for a user and gauge. """

import os
from dotenv import load_dotenv
from proofs.main import VoteMarketProofs
from shared.constants import GlobalConstants
from shared.types import UserProof, GaugeProof, BlockInfo
from eth_utils import to_checksum_address

load_dotenv()

vm_proofs = VoteMarketProofs(1)

# Example parameters
PROTOCOL = "curve"
GAUGE_ADDRESS = to_checksum_address(
    "0x059e0db6bf882f5fe680dc5409c7adeb99753736".lower()
)
USER = to_checksum_address("0xa219712cc2aaa5aa98ccf2a7ba055231f1752323".lower())
CURRENT_EPOCH = 1723680000
BLOCK_NUMBER = 20530737


def main():
    """Proof for gauge (account + storage) and user (storage only needed)"""
    # Get user proof
    user_proof: UserProof = vm_proofs.get_user_proof(
        protocol=PROTOCOL,
        gauge_address=GAUGE_ADDRESS,
        user=USER,
        block_number=BLOCK_NUMBER,
    )

    # Get gauge proof
    gauge_proof: GaugeProof = vm_proofs.get_gauge_proof(
        protocol=PROTOCOL,
        gauge_address=GAUGE_ADDRESS,
        CURRENT_EPOCH=CURRENT_EPOCH,
        block_number=BLOCK_NUMBER,
    )

    # Get block info
    block_info: BlockInfo = vm_proofs.get_block_info(BLOCK_NUMBER)

    print("Block Info:")
    print(f"Block Number: {block_info['block_number']}")
    print(f"Block Hash: {block_info['block_hash']}")
    print(f"Block Timestamp: {block_info['block_timestamp']}")
    print(f"RLP Block Header: {block_info['rlp_block_header']}")

    print("\nProof for Block (Gauge Controller):")
    print(f"0x{gauge_proof['gauge_controller_proof'].hex()}")

    print("\nProof for Gauge (Point):")
    print(f"0x{gauge_proof['point_data_proof'].hex()}")

    print("\nUser Proof (Account Data):")
    print(f"0x{user_proof['storage_proof'].hex()}")


if __name__ == "__main__":
    main()
