import os
from votemarket_proofs.VMProofs import VoteMarketProofs
from dotenv import load_dotenv

load_dotenv()

vm_proofs = VoteMarketProofs(
    "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
)

# Get user proof
user_proof = vm_proofs.get_user_proof(
    protocol="curve",
    gauge_address="0x059e0db6bf882f5fe680dc5409c7adeb99753736",
    user="0xa219712cc2aaa5aa98ccf2a7ba055231f1752323",
    current_period=1723680000,
    block_number=20530737,
)

# Get block info
block_info = vm_proofs.get_block_info(20530737)


if __name__ == "__main__":
    print(block_info)
    print("---")
    print(user_proof.hex())
