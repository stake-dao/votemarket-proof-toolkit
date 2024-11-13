import sys
from decimal import Decimal
from pathlib import Path

# Add the script directory to Python path
script_dir = str(Path(__file__).parent.parent.parent / "script")
sys.path.insert(0, script_dir)

from eth_utils import to_checksum_address
from shared.ccip_client import encode_campaign_creation_message
from shared.utils import load_json
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://ethereum.llamarpc.com"))

CCIP_ROUTER_ADDRESS = "0x80226fc0Ee2b096224EeAc085Bb9a8cba1146f7D"  # from https://docs.chain.link/ccip/directory/mainnet/chain/mainnet
MANAGER_ADDRESS = "0x8898502BA35AB64b3562aBC509Befb7Eb178D4df"
CAMPAIGN_REMOTE_MANAGER_ADDRESS = "0xd1f0101Df22Cb7447F486Da5784237AB7a55eB4e"
HOOK_ADDRESS = "0x0000000000000000000000000000000000000000"


def create_campaign(
    chain_id: int,
    gauge_address: str,
    reward_token_address: str,
    number_of_periods: int,
    max_reward_per_vote: Decimal,
    total_reward_amount: Decimal,
) -> dict:
    """
    Creates a new campaign on the specified chain using the remote manager contract.

    Args:
        chain_id: Target chain ID
        gauge_address: Address of the gauge contract
        reward_token_address: Address of the reward token
        number_of_periods: Number of periods the campaign will run
        max_reward_per_vote: Maximum reward per vote (in token units)
        total_reward_amount: Total amount of rewards for the campaign (in token units)
    """

    # Initialize contract
    campaign_remote_manager_contract = w3.eth.contract(
        address=to_checksum_address(CAMPAIGN_REMOTE_MANAGER_ADDRESS),
        abi=load_json("abi/campaign_remote_manager.json"),
    )

    # Convert decimal amounts to wei
    max_reward_per_vote_wei = w3.to_wei(max_reward_per_vote, "ether")
    total_reward_amount_wei = w3.to_wei(total_reward_amount, "ether")

    # Get CCIP fee from client
    fee = encode_campaign_creation_message(
        w3,
        to_checksum_address(CCIP_ROUTER_ADDRESS),
        chain_id,
        gauge_address,
        reward_token_address,
        number_of_periods,
        max_reward_per_vote_wei,
        total_reward_amount_wei,
        gas_limit=2_500_000,
    )

    # Add 20% buffer to CCIP fee
    fee = int(fee * 1.2)

    # Build transaction with message value for CCIP fees
    campaign_params = {
        "chainId": chain_id,
        "gauge": to_checksum_address(gauge_address),
        "manager": to_checksum_address(MANAGER_ADDRESS),
        "rewardToken": to_checksum_address(reward_token_address),
        "numberOfPeriods": number_of_periods,
        "maxRewardPerVote": max_reward_per_vote_wei,
        "totalRewardAmount": total_reward_amount_wei,
        "addresses": [],  # Empty addresses array for blacklist/whitelist
        "hook": to_checksum_address(HOOK_ADDRESS),
        "isWhitelist": False,
    }

    tx = campaign_remote_manager_contract.functions.createCampaign(
        campaign_params,
        42161,  # Destination chain id
        2_500_000,  # Additional gas limit
    ).build_transaction(
        {
            "from": to_checksum_address(MANAGER_ADDRESS),
            "gas": 2000000,
            "value": fee,  # Using CCIP fee from client
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(MANAGER_ADDRESS),
        }
    )
    return tx


# Example usage
if __name__ == "__main__":
    tx = create_campaign(
        42161,
        "0x663fc22e92f26c377ddf3c859b560c4732ee639a",
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        4,
        0.01 * 10**6,
        100000 * 10**6,
    )
    print(tx)