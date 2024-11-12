from decimal import Decimal

from web3 import Web3

from docs.examples.utils.ccip_client import encode_campaign_creation_message
from script.shared.utils import load_json

w3 = Web3(Web3.HTTPProvider("https://ethereum.llamarpc.com"))

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
    contract = w3.eth.contract(
        address=w3.to_checksum_address(CAMPAIGN_REMOTE_MANAGER_ADDRESS),
        abi=load_json("abi/campaign_remote_manager.json"),
    )

    # Convert decimal amounts to wei
    max_reward_per_vote_wei = w3.to_wei(max_reward_per_vote, "ether")
    total_reward_amount_wei = w3.to_wei(total_reward_amount, "ether")

    # Get CCIP fee from client
    fee = encode_campaign_creation_message(
        chain_id,
        gauge_address,
        reward_token_address,
        number_of_periods,
        max_reward_per_vote_wei,
        total_reward_amount_wei,
    )

    # Build transaction with message value for CCIP fees
    tx = contract.functions.createCampaign(
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
            "gas": 2000000,
            "value": fee,  # Using CCIP fee from client
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(MANAGER_ADDRESS),
        }
    )
    return tx
