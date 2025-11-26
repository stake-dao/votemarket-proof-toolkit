#!/usr/bin/env python3
"""
Example: Manage (extend) a campaign directly on L2 (Arbitrum).

This example demonstrates how to:
- Add periods and rewards to an existing campaign on L2
- Build and prepare the transaction for signing
- Handle wrapped tokens vs L2-native tokens

Usage:
    uv run examples/python/campaigns/manage_campaign_l2.py
"""

import os
from decimal import Decimal
from typing import Union

from eth_utils import to_checksum_address
from web3.exceptions import ContractLogicError

from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.utils import load_json

# Configuration
# Contract addresses
MANAGER_ADDRESS = os.getenv(
    "VOTEMARKET_MANAGER_ADDRESS", "0x8898502BA35AB64b3562aBC509Befb7Eb178D4df"
)
VOTEMARKET_ADDRESS = os.getenv(
    "VOTEMARKET_PLATFORM_ADDRESS", "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5"
)

# ABIs
VOTEMARKET_ABI = load_json("votemarket_toolkit/resources/abi/vm_platform.json")


# Helper functions
def _as_decimal(value: Union[Decimal, int, float, str]) -> Decimal:
    """Convert various numeric types to Decimal."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _scale_token_amount(
    amount: Union[Decimal, int, float, str], decimals: int
) -> int:
    """Scale a token amount to its smallest unit based on decimals."""
    decimal_amount = _as_decimal(amount)
    scaled = decimal_amount * (Decimal(10) ** decimals)
    return int(scaled.to_integral_value())


def _get_token_decimals(web3_service: Web3Service, token_address: str) -> int:
    """Fetch the number of decimals for an ERC20 token."""
    token_contract = web3_service.get_contract(token_address, "erc20")
    try:
        return token_contract.functions.decimals().call()
    except (ContractLogicError, ValueError) as exc:
        raise RuntimeError(
            f"Unable to fetch decimals for {token_address}"
        ) from exc


def manage_campaign_l2(
    campaign_id: int,
    reward_token_address: str,
    number_of_periods: int,
    max_reward_per_vote: Union[Decimal, int, float, str],
    total_reward_amount: Union[Decimal, int, float, str],
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
        reward_token_address: Address of the reward token used for the campaign
        number_of_periods: Number of periods to add
        max_reward_per_vote: New maximum reward per vote (human-readable token amount)
        total_reward_amount: Additional reward amount to add (human-readable token amount)
                           Set to 0 if only modifying periods or max reward per vote

    Returns:
        Transaction receipt
    """
    # Get Web3 service for Arbitrum (chain ID 42161)
    web3_service = Web3Service.get_instance(42161)
    w3 = web3_service.w3

    # Initialize contract
    votemarket_contract = w3.eth.contract(
        address=to_checksum_address(VOTEMARKET_ADDRESS),
        abi=VOTEMARKET_ABI,
    )

    reward_decimals = _get_token_decimals(web3_service, reward_token_address)
    max_reward_per_vote_units = _scale_token_amount(
        max_reward_per_vote, reward_decimals
    )
    total_reward_amount_units = _scale_token_amount(
        total_reward_amount, reward_decimals
    )

    # Build transaction
    tx = votemarket_contract.functions.manageCampaign(
        campaign_id,
        number_of_periods,
        total_reward_amount_units,
        max_reward_per_vote_units,
    ).build_transaction(
        {
            "from": w3.to_checksum_address(MANAGER_ADDRESS),
            "gas": 400_000,
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(MANAGER_ADDRESS),
        }
    )

    return tx


def main():
    """Example usage of managing a campaign directly on L2."""
    print("=" * 70)
    print("Managing Campaign Directly on L2 (Arbitrum)")
    print("=" * 70)

    # Management parameters
    campaign_id = 1
    reward_token = (
        "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"  # USDC on Arbitrum
    )
    periods = 4
    max_reward = Decimal("1")  # 1 USDC per vote
    total_reward = Decimal("100000")  # 100k USDC

    print("\nManagement Parameters:")
    print(f"  Campaign ID: {campaign_id}")
    print("  Chain: 42161 (Arbitrum)")
    print(f"  Reward Token: {reward_token} (USDC)")
    print(f"  Additional Periods: {periods}")
    print(f"  Max Reward/Vote: {max_reward} USDC")
    print(f"  Additional Rewards: {total_reward} USDC")

    print("\nBuilding transaction...")
    tx = manage_campaign_l2(
        campaign_id=campaign_id,
        reward_token_address=reward_token,
        number_of_periods=periods,
        max_reward_per_vote=max_reward,
        total_reward_amount=total_reward,
    )

    print("\n" + "=" * 70)
    print("Transaction Ready")
    print("=" * 70)
    print(f"  Contract: {tx['to']} (VoteMarket Platform)")
    print(f"  From: {tx['from']}")
    print(f"  Gas Limit: {tx['gas']:,}")
    print(f"  Gas Price: {tx['gasPrice']:,} wei")
    print(f"  Nonce: {tx['nonce']}")
    print(f"  Data: {tx['data']}")
    print("\nNote: Requires tokens to already be available on L2")
    print("      For wrapped tokens, you need them in your wallet")
    print("      Make sure you have approved the token spend first!")


if __name__ == "__main__":
    main()
