#!/usr/bin/env python3
"""
Example: Fetch all campaigns with periods and status.

This example demonstrates how to:
- Fetch campaigns across multiple protocols
- Retrieve campaign periods and status information
- Export campaign data to JSON format

Usage:
    uv run examples/python/campaigns/list_all.py
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from votemarket_toolkit.campaigns.service import CampaignService


async def _fetch_platform_campaigns(
    service: CampaignService, platform
) -> Tuple[Any, Optional[List[Dict[str, Any]]], Optional[str]]:
    print(
        f"Fetching {platform.protocol} {platform.version} on chain {platform.chain_id}..."
    )

    result = await service.get_campaigns(
        chain_id=platform.chain_id, platform_address=platform.address
    )
    if result.success:
        return platform, result.data, None
    else:
        error_msg = result.errors[0].message if result.errors else "Unknown error"
        return platform, None, error_msg


async def main():
    # Initialize service
    campaign_service = CampaignService()

    print("Fetching all campaigns...\n")

    all_campaigns = []

    # Get platforms for all protocols
    protocols = ["curve", "balancer", "pancakeswap", "pendle"]

    for protocol in protocols:
        platforms = campaign_service.get_all_platforms(protocol)
        tasks = [
            asyncio.create_task(
                _fetch_platform_campaigns(campaign_service, platform)
            )
            for platform in platforms
        ]

        for platform, campaigns, error in await asyncio.gather(*tasks):
            if error:
                print(
                    f"  ❌ Failed to fetch {platform.protocol} {platform.version} on chain {platform.chain_id}: {error}"
                )
                continue

            if not campaigns:
                print(
                    f"  ⚠️ No campaigns for {platform.protocol} {platform.version} on chain {platform.chain_id}"
                )
                continue

            print(f"  Found {len(campaigns)} campaigns")

            # Convert each campaign to a simple dict
            for campaign in campaigns:
                c = campaign["campaign"]
                campaign_data = {
                    "platform": f"{platform.protocol}_{platform.version}",
                    "chain_id": platform.chain_id,
                    "campaign_id": campaign["id"],
                    "gauge": c["gauge"],
                    "manager": c["manager"],
                    "reward_token": c["reward_token"],
                    "total_reward_amount": c["total_reward_amount"],
                    "is_closed": campaign["is_closed"],
                    "remaining_periods": campaign.get("remaining_periods", 0),
                    "status": campaign.get("status_info", {}).get(
                        "status", "unknown"
                    ),
                    "can_close": campaign.get("status_info", {}).get(
                        "can_close", False
                    ),
                    "who_can_close": campaign.get("status_info", {}).get(
                        "who_can_close", "no_one"
                    ),
                    "status_reason": campaign.get("status_info", {}).get(
                        "reason", ""
                    ),
                    "periods": [],
                }

                # Add period details
                for i, period in enumerate(campaign["periods"]):
                    campaign_data["periods"].append(
                        {
                            "period": i + 1,
                            "timestamp": period["timestamp"],
                            "reward_per_period": period["reward_per_period"],
                            "reward_per_vote": period["reward_per_vote"],
                        }
                    )

                all_campaigns.append(campaign_data)

    # Create output directory if it doesn't exist
    output_dir = os.path.abspath("output")
    os.makedirs(output_dir, exist_ok=True)

    # Save to file
    output_file = os.path.join(output_dir, "all_campaigns.json")
    with open(output_file, "w") as f:
        json.dump(all_campaigns, f, indent=2)

    print(f"\n✅ Saved {len(all_campaigns)} campaigns")
    print(f"   File: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
