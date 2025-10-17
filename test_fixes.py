"""
Test script to verify the fixes for the Streamlit dashboard issues.
"""
import asyncio
from votemarket_toolkit.campaigns import CampaignService
from votemarket_toolkit.shared.registry import get_platform


async def test_active_campaigns_fix():
    """Test that get_active_campaigns_by_protocol works correctly."""
    print("\n=== Testing Active Campaigns Fix ===")
    print("Testing get_active_campaigns_by_protocol method...")

    try:
        service = CampaignService()

        # Test with Curve on Arbitrum (should work)
        campaigns = await service.get_active_campaigns_by_protocol(
            protocol="curve",
            chain_id=42161,
            check_proofs=False
        )

        print(f"✅ Success! Found {len(campaigns)} active Curve campaigns on Arbitrum")

        if campaigns:
            print(f"   Example campaign: #{campaigns[0]['id']}")

        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_registry_lookup():
    """Test that registry lookup with fallback works."""
    print("\n=== Testing Registry Lookup Fix ===")
    print("Testing platform address lookup with v2/v2_old/v1 fallback...")

    try:
        # Try v2 first, then v2_old, then v1
        platform_address = get_platform("curve", 42161, "v2")
        if not platform_address:
            platform_address = get_platform("curve", 42161, "v2_old")
        if not platform_address:
            platform_address = get_platform("curve", 42161, "v1")

        if platform_address:
            print(f"✅ Success! Found platform address: {platform_address}")
            return True
        else:
            print("❌ No platform address found")
            return False

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_campaign_lookup():
    """Test that we can look up a specific campaign."""
    print("\n=== Testing Campaign Lookup ===")
    print("Testing lookup for Campaign #533 on Arbitrum...")

    try:
        service = CampaignService()

        # Get platform address
        platform_address = get_platform("curve", 42161, "v2")
        if not platform_address:
            platform_address = get_platform("curve", 42161, "v2_old")

        if not platform_address:
            print("❌ No platform address found")
            return False

        print(f"   Using platform: {platform_address}")

        # Fetch campaign #533
        campaigns = await service.get_campaigns(
            chain_id=42161,
            platform_address=platform_address,
            campaign_id=533,
            check_proofs=False
        )

        if campaigns:
            campaign = campaigns[0]
            print(f"✅ Success! Found campaign #{campaign['id']}")
            print(f"   Gauge: {campaign.get('campaign', {}).get('gauge', 'N/A')}")
            print(f"   Reward Token: {campaign.get('reward_token', {}).get('symbol', 'N/A')}")
            print(f"   Status: {campaign.get('status_info', {}).get('status', 'N/A')}")
            return True
        else:
            print("❌ Campaign #533 not found")
            return False

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("VoteMarket Toolkit - Fix Verification Tests")
    print("=" * 60)

    results = []

    # Test 1: Active campaigns by protocol
    results.append(await test_active_campaigns_fix())

    # Test 2: Registry lookup
    results.append(await test_registry_lookup())

    # Test 3: Campaign lookup
    results.append(await test_campaign_lookup())

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests passed! The fixes are working correctly.")
    else:
        print("❌ Some tests failed. Please review the errors above.")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
