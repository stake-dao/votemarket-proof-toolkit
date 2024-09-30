import os
from dotenv import load_dotenv
from proofs.main import VoteMarketProofs
from shared.types import UserProof, GaugeProof, BlockInfo

load_dotenv()

vm_proofs = VoteMarketProofs(
    "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
)

# Example parameters
PROTOCOL = "curve"
GAUGE_ADDRESS = "0x059e0db6bf882f5fe680dc5409c7adeb99753736"
USER = "0xa219712cc2aaa5aa98ccf2a7ba055231f1752323"
CURRENT_PERIOD = 1723680000
BLOCK_NUMBER = 20530737


def main():
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
        current_period=CURRENT_PERIOD,
        block_number=BLOCK_NUMBER,
    )

    # Get block info
    block_info: BlockInfo = vm_proofs.get_block_info(BLOCK_NUMBER)

    print("Block Info:")
    print(f"Block Number: {block_info['BlockNumber']}")
    print(f"Block Hash: {block_info['BlockHash']}")
    print(f"Block Timestamp: {block_info['BlockTimestamp']}")
    print(f"RLP Block Header: {block_info['RlpBlockHeader']}")

    print("\nProof for Block (Gauge Controller):")
    print(f"0x{gauge_proof['gauge_controller_proof'].hex()}")

    print("\nProof for Gauge (Point):")
    print(f"0x{gauge_proof['point_data_proof'].hex()}")

    print("\nUser Proof (Account Data):")
    print(f"0x{user_proof['storage_proof'].hex()}")


if __name__ == "__main__":
    main()
