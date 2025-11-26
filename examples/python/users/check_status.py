#!/usr/bin/env python3
"""
Example: Check user proof status for VoteMarket campaigns.

This example demonstrates how to:
- Check if a user can claim rewards from campaigns
- Verify if proofs are inserted on-chain
- Check claim eligibility for each period
- Get detailed proof status information

Note: Users can only claim rewards if they:
1. Voted for the campaign's gauge during the campaign period
2. Have their vote proof data uploaded to the oracle
3. Have block and point data uploaded (usually done automatically)

Usage:
    uv run examples/python/users/check_status.py
"""

import asyncio

from web3.exceptions import ContractLogicError

# VoteMarket toolkit imports
from votemarket_toolkit.campaigns.service import CampaignService
from votemarket_toolkit.shared import registry


async def check_user_campaign_status(
    user_address: str,
    campaign_id: int,
    chain_id: int = 42161,  # Default to Arbitrum
    platform_name: str = "curve",
    version: str = "v2",
) -> None:
    """
    Check if a user has all necessary proofs for claiming rewards.

    Args:
        user_address: User's address to check
        campaign_id: Campaign ID to check
        chain_id: Chain ID (default: 42161 for Arbitrum)
        platform_name: Protocol name (default: curve)
        version: Platform version (default: v2)
    """
    # Get platform address
    platform = registry.get_platform(
        platform_name, chain_id=chain_id, version=version
    )
    if not platform:
        print(
            f"Platform not found: {platform_name} {version} on chain {chain_id}"
        )
        return

    print(
        f"\nChecking campaign #{campaign_id} for user {user_address[:10]}..."
    )

    service = CampaignService()

    try:
        # Get campaign with proof status
        campaigns = await service.get_campaigns(
            chain_id=chain_id,
            platform_address=platform,
            campaign_id=campaign_id,
            check_proofs=True,  # Important: enables proof checking
        )

        if not campaigns:
            print(f"  ❌ Campaign #{campaign_id} not found")
            return

        campaign = campaigns[0]

        # Get user-specific proof status
        proof_status = await service.get_user_campaign_proof_status(
            chain_id=chain_id,
            platform_address=platform,
            campaign=campaign,
            user_address=user_address,
        )

        # Display campaign info
        print(f"  Gauge: {campaign['campaign']['gauge'][:10]}...")
        print(f"  Status: {'Closed' if campaign['is_closed'] else 'Active'}")
        print(f"  Total Periods: {len(campaign.get('periods', []))}")

        if proof_status and proof_status.get("periods"):
            # Calculate summary
            periods = proof_status["periods"]
            total_periods = len(periods)
            claimable_periods = [
                p for p in periods if p.get("is_claimable", False)
            ]
            claimable_count = len(claimable_periods)
            can_claim_all = claimable_count == total_periods

            print(
                f"\n  Claim Status: {'✅ Ready' if can_claim_all else '❌ Not Ready'}"
            )
            print(f"  Claimable: {claimable_count}/{total_periods} periods")

            # Show period details if not all claimable
            if not can_claim_all:
                print("\n  Period Details:")
                for idx, period in enumerate(periods):
                    if not period.get("is_claimable", False):
                        missing = []
                        if not period.get("block_updated"):
                            missing.append("block")
                        if not period.get("point_data_inserted"):
                            missing.append("gauge data")
                        if not period.get("user_slope_inserted"):
                            missing.append("user vote")

                        print(
                            f"    Period {idx + 1}: Missing {', '.join(missing)}"
                        )
        else:
            print("  ⚠️  Unable to fetch proof status")

    except (ContractLogicError, ValueError, RuntimeError) as exc:
        print(f"  ❌ Error: {str(exc)[:100]}")
    except Exception:
        raise


async def main():
    """Run the example with sample data."""
    print("=== VoteMarket Example: Check User Proof Status ===")

    # Example configuration
    user_address = "0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6"
    campaign_ids = [97, 98, 99]

    print(f"\nChecking campaigns for user {user_address}")
    print("-" * 60)

    # Check each campaign
    for campaign_id in campaign_ids:
        await check_user_campaign_status(
            user_address=user_address,
            campaign_id=campaign_id,
            chain_id=42161,
            platform_name="curve",
            version="v2",
        )

    print("\n✅ Example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
