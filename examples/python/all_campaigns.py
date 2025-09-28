#!/usr/bin/env python3
"""
Fetch all campaigns with periods and status.
"""

import asyncio
import json
from votemarket_toolkit.campaigns.service import CampaignService


async def main():
    # Initialize service
    campaign_service = CampaignService()

    print("Fetching all campaigns...\n")

    all_campaigns = []

    # Get platforms for all protocols
    protocols = ["curve", "balancer", "pancakeswap", "pendle"]

    for protocol in protocols:
        platforms = campaign_service.get_all_platforms(protocol)

        for platform in platforms:
            print(
                f"Fetching {platform.protocol} {platform.version} on chain {platform.chain_id}..."
            )

            # Get campaigns for this platform
            campaigns = await campaign_service.get_campaigns(
                chain_id=platform.chain_id, platform_address=platform.address
            )

            if campaigns:
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
                        "status": campaign["status_info"]["status"].value,
                        "is_closed": campaign["is_closed"],
                        "periods": [],
                    }

                    # Add period details
                    for i, period in enumerate(campaign["periods"]):
                        campaign_data["periods"].append(
                            {
                                "period": i + 1,
                                "timestamp": period["timestamp"],
                                "reward_per_period": period[
                                    "reward_per_period"
                                ],
                                "reward_per_vote": period["reward_per_vote"],
                            }
                        )

                    all_campaigns.append(campaign_data)

    # Save to file
    with open("output/all_campaigns.json", "w") as f:
        json.dump(all_campaigns, f, indent=2)

    print(f"\n✅ Saved {len(all_campaigns)} campaigns to all_campaigns.json")


if __name__ == "__main__":
    asyncio.run(main())
