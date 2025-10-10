#!/usr/bin/env python3
"""
Example: Close a campaign and optionally bridge rewards back to L1.

This example demonstrates how to:
- Close a completed campaign
- Optionally bridge remaining rewards back to L1
- Handle both L1 and L2 campaign closures

Usage:
    uv run examples/python/campaigns/close_campaign.py
"""

import os

from eth_utils import to_checksum_address

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


def close_campaign(campaign_id: int, bridge_back: bool = False) -> dict:
    """
    Close a campaign and optionally bridge rewards back to L1.

    Args:
        campaign_id: ID of the campaign to close
        bridge_back: If True, bridge remaining rewards back to L1 (default: False)

    Returns:
        Transaction dictionary ready to be signed and sent
    """
    # Get Web3 service for Arbitrum (chain ID 42161)
    web3_service = Web3Service.get_instance(42161)
    w3 = web3_service.w3

    # Initialize contract
    votemarket_contract = w3.eth.contract(
        address=to_checksum_address(VOTEMARKET_ADDRESS),
        abi=VOTEMARKET_ABI,
    )

    # Build transaction
    tx = votemarket_contract.functions.closeCampaign(
        campaign_id,
        bridge_back,  # Whether to bridge remaining rewards back to L1
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
    """Example usage of closing a campaign."""
    campaign_id = 123

    # Example 1: Close campaign without bridging back
    print("=" * 70)
    print("Example 1: Close Campaign (Keep Rewards on L2)")
    print("=" * 70)
    print(f"\nCampaign ID: {campaign_id}")
    print("Bridge back to L1: No")

    print("\nBuilding transaction...")
    tx1 = close_campaign(
        campaign_id=campaign_id,
        bridge_back=False,
    )

    print("\n" + "=" * 70)
    print("Transaction Ready")
    print("=" * 70)
    print(f"  Contract: {tx1['to']} (VoteMarket Platform)")
    print(f"  From: {tx1['from']}")
    print(f"  Gas Limit: {tx1['gas']:,}")
    print(f"  Gas Price: {tx1['gasPrice']:,} wei")
    print(f"  Nonce: {tx1['nonce']}")
    print(f"  Data: {tx1['data']}")
    print("\nNote: Remaining rewards will stay on L2 in wrapped token form")

    # Example 2: Close campaign and bridge rewards back to L1
    print("\n\n" + "=" * 70)
    print("Example 2: Close Campaign (Bridge Rewards Back to L1)")
    print("=" * 70)
    print(f"\nCampaign ID: {campaign_id}")
    print("Bridge back to L1: Yes")

    print("\nBuilding transaction...")
    tx2 = close_campaign(
        campaign_id=campaign_id,
        bridge_back=True,
    )

    print("\n" + "=" * 70)
    print("Transaction Ready")
    print("=" * 70)
    print(f"  Contract: {tx2['to']} (VoteMarket Platform)")
    print(f"  From: {tx2['from']}")
    print(f"  Gas Limit: {tx2['gas']:,}")
    print(f"  Gas Price: {tx2['gasPrice']:,} wei")
    print(f"  Nonce: {tx2['nonce']}")
    print(f"  Data: {tx2['data']}")
    print("\nNote: Remaining rewards will be bridged back to L1 via CCIP")
    print("      Additional CCIP fees will be charged")


if __name__ == "__main__":
    main()
