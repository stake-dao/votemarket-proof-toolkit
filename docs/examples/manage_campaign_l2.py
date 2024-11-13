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
VOTEMARKET_ABI = load_json("abi/vm_platform.json")


def manage_campaign_l2(
    campaign_id: int,
    number_of_periods: int,
    max_reward_per_vote: Decimal,
    total_reward_amount: Decimal,
) -> dict:
    """
    Manages an existing campaign directly on L2 (Arbitrum).

    IMPORTANT: For wrapped tokens (L1 tokens bridged to L2):
    - You need to have wrapped tokens in your wallet, which you can get by:
        a) Claiming rewards yourself from previous campaigns
        b) Closing a campaign without bridging back to L1
    - If you don't have some wrapped tokens, use the L1 campaign management function instead,
      which will handle the bridging of tokens automatically.

    Args:
        campaign_id: ID of the campaign to manage
        number_of_periods: Number of periods to add
        max_reward_per_vote: New maximum reward per vote (in token units)
        total_reward_amount: Additional reward amount to add (in token units)
                           Set to 0 if only modifying periods or max reward per vote

    Returns:
        Transaction receipt
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
    tx = votemarket_contract.functions.manageCampaign(
        campaign_id,
        number_of_periods,
        total_reward_amount_wei,
        max_reward_per_vote_wei,
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
    tx = manage_campaign_l2(1, 4, 1 * 10**6, 100000 * 10**6)
    print(tx)
