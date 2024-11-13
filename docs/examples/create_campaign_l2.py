import sys
from decimal import Decimal
from pathlib import Path

# Add the script directory to Python path
script_dir = str(Path(__file__).parent.parent.parent / "script")
sys.path.insert(0, script_dir)

from eth_utils import to_checksum_address
from shared.utils import load_json
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://arb1.arbitrum.io/rpc"))

MANAGER_ADDRESS = "0x8898502BA35AB64b3562aBC509Befb7Eb178D4df"
VOTEMARKET_ADDRESS = "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5"
HOOK_ADDRESS = "0x0000000000000000000000000000000000000000"
VOTEMARKET_ABI = load_json("abi/vm_platform.json")


def create_campaign_l2(
    chain_id: int,
    gauge_address: str,
    reward_token_address: str,
    number_of_periods: int,
    max_reward_per_vote: Decimal,
    total_reward_amount: Decimal,
) -> dict:
    """
    Creates a new campaign directly on L2 (Arbitrum).

    Args:
        chain_id: Chain ID (should be Arbitrum's chain ID)
        gauge_address: Address of the gauge contract
        reward_token_address: Address of the reward token
        number_of_periods: Number of periods the campaign will run
        max_reward_per_vote: Maximum reward per vote (in token units)
        total_reward_amount: Total amount of rewards for the campaign (in token units)
    """

    # Initialize contract
    votemarket_contract = w3.eth.contract(
        address=to_checksum_address(VOTEMARKET_ADDRESS),
        abi=VOTEMARKET_ABI,
    )

    # Convert decimal amounts to wei
    max_reward_per_vote_wei = w3.to_wei(max_reward_per_vote, "ether")
    total_reward_amount_wei = w3.to_wei(total_reward_amount, "ether")

    # Build transaction
    tx = votemarket_contract.functions.createCampaign(
        chain_id,
        w3.to_checksum_address(gauge_address),
        w3.to_checksum_address(MANAGER_ADDRESS),
        w3.to_checksum_address(reward_token_address),
        number_of_periods,
        max_reward_per_vote_wei,
        total_reward_amount_wei,
        [],  # Empty addresses array for blacklist/whitelist
        w3.to_checksum_address(HOOK_ADDRESS),
        False,  # isWhitelist
    ).build_transaction(
        {
            "from": w3.to_checksum_address(MANAGER_ADDRESS),
            "gas": 400_000,
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(MANAGER_ADDRESS),
        }
    )
    return tx


if __name__ == "__main__":
    tx = create_campaign_l2(
        42161,
        "0x663fc22e92f26c377ddf3c859b560c4732ee639a",
        "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        4,
        0.01 * 10**6,
        100000 * 10**6,
    )
    print(tx)
