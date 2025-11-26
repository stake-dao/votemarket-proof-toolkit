#!/usr/bin/env python3
"""
Example: Get all campaigns managed by a specific address.

This example demonstrates how to:
- Search for campaigns by manager address
- Filter by protocol and active status
- Display campaign details and status

Usage:
    uv run examples/python/campaigns/by_manager.py
"""

import asyncio

from votemarket_toolkit.campaigns.service import CampaignService


async def main():
    """Fetch and display campaigns managed by a specific address."""
    # Initialize service
    service = CampaignService()

    manager_address = "0x5EeDA5BDF0A647a7089329428009eCc9CB9451cc"

    # Get all campaigns for this manager across all Curve platforms
    print(f"Searching for campaigns managed by {manager_address}...")

    results = await service.get_campaigns_by_manager(
        protocol="curve",
        manager_address=manager_address,
        active_only=True,  # Only check active platforms for speed
    )

    # Display results
    if not results:
        print("No campaigns found for this manager")
    else:
        total_campaigns = sum(len(campaigns) for campaigns in results.values())
        print(
            f"\nFound {total_campaigns} campaigns across {len(results)} platforms:\n"
        )

        for platform, campaigns in results.items():
            print(f"{platform}: {len(campaigns)} campaigns")

            for campaign in campaigns:
                # Campaign ID is at top level
                campaign_id = campaign.get("id", "Unknown")

                # Campaign details are nested
                c = campaign.get("campaign", {})
                if not c:
                    continue

                gauge = c.get("gauge", "Unknown")
                total_reward = c.get("total_reward_amount", 0)

                # Token info
                token = campaign.get("reward_token", {})
                token_symbol = token.get("symbol", "Unknown")
                decimals = token.get("decimals", 18)

                # Status
                status = "CLOSED" if campaign.get("is_closed") else "ACTIVE"
                remaining = campaign.get("remaining_periods", 0)
                total_periods = c.get("number_of_periods", 0)

                print(
                    f"  - Campaign #{campaign_id}: {token_symbol} - {status}"
                )
                print(f"    Gauge: {gauge}")
                print(f"    Periods: {remaining}/{total_periods} remaining")

                if total_reward > 0:
                    amount = total_reward / (10**decimals)
                    print(f"    Rewards: {amount:.2f} {token_symbol}")


if __name__ == "__main__":
    asyncio.run(main())
