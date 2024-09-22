import os
from votemarket_proofs.VMProofs import VoteMarketProofs
from dotenv import load_dotenv

load_dotenv()

vm_proofs = VoteMarketProofs(
    "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
)

# Example parameters
protocol = "curve"
gauge_address = "0x059e0db6bf882f5fe680dc5409c7adeb99753736"
user = "0xa219712cc2aaa5aa98ccf2a7ba055231f1752323"
current_period = 1723680000
block_number = 20530737

# Get user proof
user_account_proof, user_storage_proof = vm_proofs.get_user_proof(
    protocol=protocol,
    gauge_address=gauge_address,
    user=user,
    block_number=block_number,
)

# Get gauge proof
gauge_account_proof, gauge_storage_proof = vm_proofs.get_gauge_proof(
    protocol=protocol,
    gauge_address=gauge_address,
    current_period=current_period,
    block_number=block_number,
)

# Get block info
block_info = vm_proofs.get_block_info(block_number)

if __name__ == "__main__":
    print("User Proof:")
    print(f"Account Proof: {user_account_proof.hex()}")
    print(f"Storage Proof: {user_storage_proof.hex()}")
    print("\nGauge Proof:")
    print(f"Account Proof: {gauge_account_proof.hex()}")
    print(f"Storage Proof: {gauge_storage_proof.hex()}")
    print("\nBlock Info:")
    print(f"Block Number: {block_info['BlockNumber']}")
    print(f"Block Hash: {block_info['BlockHash']}")
    print(f"Block Timestamp: {block_info['BlockTimestamp']}")
    print(f"RLP Block Header: {block_info['RlpBlockHeader']}")


# Integrate an interaction (set data in Oracle, Claim) with Votemarket (+ multicall)