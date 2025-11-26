#!/usr/bin/env python3
"""
Example: Create a campaign directly on L2 (Arbitrum).

This example demonstrates how to:
- Create a campaign directly on L2 without bridging from L1
- Build and prepare the transaction for signing
- Handle token decimals and amounts correctly

Usage:
    uv run examples/python/campaigns/create_campaign_l2.py
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
HOOK_ADDRESS = os.getenv(
    "VOTEMARKET_HOOK_ADDRESS", "0x0000000000000000000000000000000000000000"
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
        max_reward_per_vote: Maximum reward per vote (human-readable token amount)
        total_reward_amount: Total amount of rewards for the campaign (human-readable token amount)
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
    tx = votemarket_contract.functions.createCampaign(
        chain_id,
        w3.to_checksum_address(gauge_address),
        w3.to_checksum_address(MANAGER_ADDRESS),
        w3.to_checksum_address(reward_token_address),
        number_of_periods,
        max_reward_per_vote_units,
        total_reward_amount_units,
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


def main():
    """Example usage of creating a campaign directly on L2."""
    print("=" * 70)
    print("Creating Campaign Directly on L2 (Arbitrum)")
    print("=" * 70)

    # Campaign parameters
    chain_id = 42161  # Arbitrum
    gauge_address = "0x663fc22e92f26c377ddf3c859b560c4732ee639a"
    reward_token = (
        "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"  # USDC on Arbitrum
    )
    periods = 4
    max_reward = Decimal("0.01")  # 0.01 USDC per vote
    total_reward = Decimal("100000")  # 100k USDC

    print("\nCampaign Parameters:")
    print(f"  Chain: {chain_id} (Arbitrum)")
    print(f"  Gauge: {gauge_address}")
    print(f"  Reward Token: {reward_token} (USDC)")
    print(f"  Periods: {periods}")
    print(f"  Max Reward/Vote: {max_reward} USDC")
    print(f"  Total Rewards: {total_reward} USDC")

    print("\nBuilding transaction...")
    tx = create_campaign_l2(
        chain_id=chain_id,
        gauge_address=gauge_address,
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
    print("      Make sure you have approved the token spend first!")


if __name__ == "__main__":
    main()
