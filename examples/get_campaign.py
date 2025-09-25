#!/usr/bin/env python3
"""
Simple example to fetch VoteMarket campaign data.

Usage:
    python get_campaign.py <protocol> <campaign_id> [platform_address]

Examples:
    python get_campaign.py curve 3
    python get_campaign.py curve 3 0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5
"""

import sys
import os
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.votemarket_toolkit.campaigns.services.campaign_service import (
    CampaignService,
)
from src.votemarket_toolkit.shared import registry


async def get_campaign(protocol, campaign_id, platform_address=None):
    """
    Get a campaign by protocol and ID.

    Args:
        protocol: Protocol name (curve, balancer, etc)
        campaign_id: Campaign ID number
        platform_address: Optional specific platform address

    Returns:
        Campaign data or None
    """
    service = CampaignService()

    if platform_address:
        # Use specific platform
        print(
            f"Fetching campaign #{campaign_id} from platform {platform_address[:10]}..."
        )

        # Find chain for this platform
        all_platforms = registry.get_all_platforms(protocol)
        platform_info = None
        for p in all_platforms:
            if p["address"].lower() == platform_address.lower():
                platform_info = p
                break

        if not platform_info:
            print(f"Platform {platform_address} not found for {protocol}")
            return None, None

        campaigns = await service.get_campaigns(
            platform_address=platform_address,
            chain_id=platform_info["chain_id"],
            campaign_id=campaign_id,
            check_proofs=True,
        )

        if campaigns:
            return campaigns[0], platform_info

    else:
        # Search all platforms
        print(
            f"Searching for campaign #{campaign_id} in {protocol} platforms..."
        )

        all_platforms = registry.get_all_platforms(protocol)
        print(f"Found {len(all_platforms)} platforms to check")

        for platform in all_platforms:
            print(
                f"  Checking {platform['version']} on chain {platform['chain_id']}..."
            )

            campaigns = await service.get_campaigns(
                platform_address=platform["address"],
                chain_id=platform["chain_id"],
                campaign_id=campaign_id,
                check_proofs=True,  # Always check proofs for complete data
            )

            if campaigns:
                print(f"  ✓ Found campaign!")
                return campaigns[0], platform

        print(f"Campaign #{campaign_id} not found in any {protocol} platform")

    return None, None


def display_campaign(campaign, platform_info):
    """Display campaign information."""
    if not campaign:
        return

    print("\n" + "=" * 60)
    print("CAMPAIGN DETAILS")
    print("=" * 60)

    # Basic info
    print(f"Campaign ID: {campaign['id']}")
    print(f"Platform: {platform_info['address']} ({platform_info['version']})")
    print(f"Chain: {platform_info['chain_id']}")

    # Campaign details
    c = campaign["campaign"]
    print(f"\nGauge: {c['gauge']}")
    print(f"Manager: {c['manager']}")
    print(f"Reward Token: {c['reward_token']}")
    print(f"Total Reward: {c['total_reward_amount'] / 1e18:.2f}")
    print(f"Number of Periods: {c['number_of_periods']}")

    # Status with detailed information
    status_info = campaign.get("status_info", {})
    if status_info:
        print(f"\nStatus: {status_info.get('reason', 'Unknown')}")
        print(f"  Can Close: {status_info.get('can_close', False)}")
        print(f"  Who Can Close: {status_info.get('who_can_close', 'no_one')}")
        if (
            status_info.get("days_until_public_close") is not None
            and status_info.get("days_until_public_close") > 0
        ):
            print(
                f"  Days Until Public Close: {status_info['days_until_public_close']}"
            )
    else:
        print(f"\nStatus: {'Closed' if campaign['is_closed'] else 'Active'}")

    print(f"Whitelist Only: {campaign['is_whitelist_only']}")
    print(f"Remaining Periods: {campaign.get('remaining_periods', 0)}")

    # Periods with proof status
    periods = campaign.get("periods", [])
    print(f"\nPeriods ({len(periods)} total):")
    for i, period in enumerate(periods):
        reward = period["reward_per_period"] / 1e18
        per_vote = period["reward_per_vote"] / 1e18

        # Check proof status
        updated = "✓" if period.get("updated", False) else "✗"
        proof_inserted = (
            "✓" if period.get("point_data_inserted", False) else "✗"
        )
        block_updated = "✓" if period.get("block_updated", False) else "✗"

        print(f"  Period {i+1}: {reward:.2f} rewards, {per_vote:.6f} per vote")
        print(
            f"           Updated: {updated} | Proof: {proof_inserted} | Block: {block_updated}"
        )

    # Save to file
    os.makedirs("temp", exist_ok=True)
    filename = (
        f"temp/campaign_{campaign['id']}_{platform_info['version']}.json"
    )
    with open(filename, "w") as f:
        json.dump(
            {"campaign": campaign, "platform": platform_info},
            f,
            indent=2,
            default=str,
        )

    print(f"\nSaved to: {filename}")


async def main():
    """Main function."""

    # Parse arguments
    if len(sys.argv) < 3:
        print(
            "Usage: python get_campaign.py <protocol> <campaign_id> [platform_address]"
        )
        print("\nExamples:")
        print("  python get_campaign.py curve 3")
        print(
            "  python get_campaign.py curve 3 0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5"
        )
        sys.exit(1)

    protocol = sys.argv[1]
    campaign_id = int(sys.argv[2])
    platform_address = sys.argv[3] if len(sys.argv) > 3 else None

    # Get campaign
    campaign, platform = await get_campaign(
        protocol, campaign_id, platform_address
    )

    if campaign:
        display_campaign(campaign, platform)
    else:
        print(f"\nCampaign not found")


if __name__ == "__main__":
    asyncio.run(main())
