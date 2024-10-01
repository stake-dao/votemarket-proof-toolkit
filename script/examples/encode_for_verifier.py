"""Example encoding data to be passed on the Verifier Contract."""

import os
from dotenv import load_dotenv
from eth_utils import to_checksum_address
from proofs.main import VoteMarketProofs
from shared.types import UserProof, GaugeProof, BlockInfo
from shared.web3_service import get_web3_service

load_dotenv()

# Initialize VoteMarket services
vm_proofs = VoteMarketProofs(
    1, "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
)

web3_service = get_web3_service()

# Example parameters
PROTOCOL = "curve"
GAUGE_ADDRESS = to_checksum_address(
    "0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A"
)  # sdCRV gauge
BLOCK_NUMBER = 20864159
CURRENT_PERIOD = 1723680000
USER = to_checksum_address("0xa219712cc2aaa5aa98ccf2a7ba055231f1752323")


def main():
    """All possibles interactions"""
    # Get necessary proofs and info
    block_info: BlockInfo = vm_proofs.get_block_info(BLOCK_NUMBER)
    gauge_proof: GaugeProof = vm_proofs.get_gauge_proof(
        PROTOCOL, GAUGE_ADDRESS, CURRENT_PERIOD, BLOCK_NUMBER
    )
    user_proof: UserProof = vm_proofs.get_user_proof(
        PROTOCOL, GAUGE_ADDRESS, USER, BLOCK_NUMBER
    )

    # Initialize Verifier contract
    verifier_address = to_checksum_address(
        "0x348d1bd2a18c9a93eb9ab8e5f55852da3036e225"
    )  # Arbitrum example one
    verifier = web3_service.get_contract(verifier_address, "verifier", 42161)

    # Encode data for setBlockData (block must be set on the oracle first)
    block_data_input = verifier.encodeABI(
        fn_name="setBlockData",
        args=[block_info["RlpBlockHeader"], gauge_proof["gauge_controller_proof"]],
    )
    print("Encoded data for setBlockData:")
    print(block_data_input)

    # Encode data for setPointData
    point_data_input = verifier.encodeABI(
        fn_name="setPointData",
        args=[GAUGE_ADDRESS, CURRENT_PERIOD, gauge_proof["point_data_proof"]],
    )
    print("\nEncoded data for setPointData:")
    print(point_data_input)

    # Encode data for setAccountData
    account_data_input = verifier.encodeABI(
        fn_name="setAccountData",
        args=[USER, GAUGE_ADDRESS, CURRENT_PERIOD, user_proof["storage_proof"]],
    )
    print("\nEncoded data for setAccountData:")
    print(account_data_input)


if __name__ == "__main__":
    main()
