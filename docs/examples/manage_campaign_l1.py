import sys
from decimal import Decimal
from pathlib import Path

# Add the script directory to Python path
script_dir = str(Path(__file__).parent.parent.parent / "script")
sys.path.insert(0, script_dir)

from eth_utils import to_checksum_address
from shared.ccip_client import encode_campaign_management_message
from shared.utils import load_json
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://ethereum.llamarpc.com"))

MANAGER_ADDRESS = "0x8898502BA35AB64b3562aBC509Befb7Eb178D4df"
CAMPAIGN_REMOTE_MANAGER_ADDRESS = "0xd1f0101Df22Cb7447F486Da5784237AB7a55eB4e"
CCIP_ROUTER_ADDRESS = "0x80226fc0Ee2b096224EeAc085Bb9a8cba1146f7D"  # from https://docs.chain.link/ccip/directory/mainnet/chain/mainnet


def manage_campaign(
    chain_id: int,
    campaign_id: int,
    reward_token_address: str,
    number_of_periods: int,
    max_reward_per_vote: Decimal,
    total_reward_amount: Decimal,
) -> dict:
    """
    Manages an existing campaign through the remote manager contract.

    Args:
        chain_id: Target chain ID
        campaign_id: ID of the campaign to manage
        reward_token_address: Address of the reward token
        number_of_periods: Number of periods to extend
        max_reward_per_vote: Maximum reward per vote (in token units)
        total_reward_amount: Total amount of rewards to add (in token units)
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
    fee = encode_campaign_management_message(
        w3,
        to_checksum_address(CCIP_ROUTER_ADDRESS),
        chain_id,
        campaign_id,
        reward_token_address,
        number_of_periods,
        total_reward_amount_wei,
        max_reward_per_vote_wei,
        200_000,
    )

    # Add 20% buffer to CCIP fee
    fee = int(fee * 1.2)

    # Build management parameters struct
    management_params = {
        "campaignId": campaign_id,
        "rewardToken": to_checksum_address(reward_token_address),
        "numberOfPeriods": number_of_periods,
        "totalRewardAmount": total_reward_amount_wei,
        "maxRewardPerVote": max_reward_per_vote_wei,
    }

    # Build transaction with message value for CCIP fees
    tx = campaign_remote_manager_contract.functions.manageCampaign(
        management_params,
        42161,  # Destination chain id
        200_000,  # Additional gas limit
    ).build_transaction(
        {
            "from": to_checksum_address(MANAGER_ADDRESS),
            "gas": 200_000,
            "value": fee,  # Using CCIP fee from client
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(MANAGER_ADDRESS),
        }
    )
    return tx


# Example usage
if __name__ == "__main__":
    tx = manage_campaign(
        42161,  # chain_id
        1,  # campaign_id
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
        4,  # number_of_periods
        1 * 10**6,
        100000 * 10**6,
    )
    print(tx)
