#!/usr/bin/env python3
"""
Example: Manage (extend) a campaign on L2 from L1 using CCIP bridge.

This example demonstrates how to:
- Add periods and rewards to an existing campaign from L1
- Calculate CCIP fees for cross-chain messaging
- Build and prepare the transaction for signing

Usage:
    uv run examples/python/campaigns/manage_campaign_l1.py
"""

import os
from decimal import Decimal
from typing import Union

from eth_utils import to_checksum_address
from web3.exceptions import ContractLogicError

from votemarket_toolkit.shared.services.ccip_fee_service import CcipFeeService
from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.utils import load_json

# Configuration
# Contract addresses
CCIP_ROUTER_ADDRESS = os.getenv(
    "CCIP_ROUTER_ADDRESS", "0x80226fc0Ee2b096224EeAc085Bb9a8cba1146f7D"
)
MANAGER_ADDRESS = os.getenv(
    "VOTEMARKET_MANAGER_ADDRESS", "0x8898502BA35AB64b3562aBC509Befb7Eb178D4df"
)
CAMPAIGN_REMOTE_MANAGER_ADDRESS = os.getenv(
    "VOTEMARKET_REMOTE_MANAGER_ADDRESS",
    "0x53aD4Cd1F1e52DD02aa9FC4A8250A1b74F351CA2",
)


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
        max_reward_per_vote: Maximum reward per vote (human-readable token amount)
        total_reward_amount: Total amount of rewards to add (human-readable token amount)
    """
    # Get Web3 service for Ethereum mainnet (chain ID 1)
    web3_service = Web3Service.get_instance(1)
    w3 = web3_service.w3

    fee_calculator = CcipFeeService(w3, CCIP_ROUTER_ADDRESS)

    # Initialize contract
    campaign_remote_manager_contract = w3.eth.contract(
        address=to_checksum_address(CAMPAIGN_REMOTE_MANAGER_ADDRESS),
        abi=load_json(
            "votemarket_toolkit/resources/abi/campaign_remote_manager.json"
        ),
    )

    # Convert decimal amounts to wei
    reward_decimals = _get_token_decimals(web3_service, reward_token_address)
    max_reward_per_vote_units = _scale_token_amount(
        max_reward_per_vote, reward_decimals
    )
    total_reward_amount_units = _scale_token_amount(
        total_reward_amount, reward_decimals
    )

    # Using contract utils to get CCIP fee
    fee = fee_calculator.get_ccip_fee(
        dest_chain_id=chain_id,
        execution_gas_limit=200_000,
        receiver=to_checksum_address(MANAGER_ADDRESS),
        tokens=[
            {
                "address": to_checksum_address(reward_token_address),
                "amount": total_reward_amount_units,
            },
        ],
        additional_data=b"",
    )

    # Build management parameters struct
    management_params = {
        "campaignId": campaign_id,
        "rewardToken": to_checksum_address(reward_token_address),
        "numberOfPeriods": number_of_periods,
        "totalRewardAmount": total_reward_amount_units,
        "maxRewardPerVote": max_reward_per_vote_units,
    }

    # Build transaction with message value for CCIP fees
    tx = campaign_remote_manager_contract.functions.manageCampaign(
        management_params,
        chain_id,  # Destination chain id
        200_000,
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


def main():
    """Example usage of managing a campaign from L1."""
    print("=" * 70)
    print("Managing Campaign on L2 from L1 (via CCIP)")
    print("=" * 70)

    # Get Web3 service for display purposes
    web3_service = Web3Service.get_instance(1)

    # Management parameters
    chain_id = 42161  # Arbitrum
    campaign_id = 1
    reward_token = (
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC on Ethereum
    )
    periods = 4
    max_reward = Decimal("1")  # 1 USDC per vote
    total_reward = Decimal("100000")  # 100k USDC

    print("\nManagement Parameters:")
    print(f"  Campaign ID: {campaign_id}")
    print(f"  Destination Chain: {chain_id} (Arbitrum)")
    print(f"  Reward Token: {reward_token} (USDC)")
    print(f"  Additional Periods: {periods}")
    print(f"  Max Reward/Vote: {max_reward} USDC")
    print(f"  Additional Rewards: {total_reward} USDC")

    print("\nBuilding transaction...")
    tx = manage_campaign(
        chain_id=chain_id,
        campaign_id=campaign_id,
        reward_token_address=reward_token,
        number_of_periods=periods,
        max_reward_per_vote=max_reward,
        total_reward_amount=total_reward,
    )

    print("\n" + "=" * 70)
    print("Transaction Ready")
    print("=" * 70)
    print(f"  Contract: {tx['to']} (CampaignRemoteManager)")
    print(f"  From: {tx['from']}")
    print(
        f"  Value: {tx['value']} wei ({web3_service.w3.from_wei(tx['value'], 'ether'):.6f} ETH)"
    )
    print(f"  Gas Limit: {tx['gas']:,}")
    print(f"  Gas Price: {tx['gasPrice']:,} wei")
    print(f"  Nonce: {tx['nonce']}")
    print(f"  Data: {tx['data']}")
    print(
        "\nNote: This transaction will bridge additional tokens from L1 to L2 using CCIP"
    )
    print("      Make sure you have approved the token spend first!")


if __name__ == "__main__":
    main()
