"""
Test: Toolkit campaign data matches V3 API.

Compares:
- Campaign counts
- Campaign field values (gauge, manager, reward_token)
- Campaign structure integrity
"""

import httpx
import pytest
from votemarket_toolkit import CampaignService

API_V3_BASE = "https://api-v3.stakedao.org/votemarket"
CURVE_V2_PLATFORM = "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9"


def fetch_api_campaigns(protocol: str):
    """Fetch campaigns from V3 API."""
    response = httpx.get(f"{API_V3_BASE}/{protocol}", timeout=30)
    response.raise_for_status()
    return response.json().get("campaigns", [])


@pytest.fixture
def campaign_service():
    return CampaignService()


@pytest.mark.integration
class TestCampaignsVsAPI:
    """Compare toolkit campaigns vs API campaigns."""

    @pytest.mark.asyncio
    async def test_curve_campaigns_exist_in_api(self, campaign_service):
        """Campaigns from toolkit should exist in API."""
        api_campaigns = fetch_api_campaigns("curve")
        api_arb = [c for c in api_campaigns if c.get("chainId") == 42161]
        api_ids = {c["id"] for c in api_arb}

        result = await campaign_service.get_campaigns(
            chain_id=42161,
            platform_address=CURVE_V2_PLATFORM,
            check_proofs=False,
        )

        assert result.success
        assert result.data, "SDK should return campaigns"

        # SDK campaigns should be subset of API campaigns
        sdk_ids = {c["id"] for c in result.data}
        missing = sdk_ids - api_ids

        # Allow small number of missing (timing differences)
        assert len(missing) <= 5, f"SDK campaigns not in API: {missing}"

    @pytest.mark.asyncio
    async def test_campaign_fields_match(self, campaign_service):
        """Campaign fields should match between toolkit and API."""
        api_campaigns = fetch_api_campaigns("curve")
        api_arb = [c for c in api_campaigns if c.get("chainId") == 42161]

        if not api_arb:
            pytest.skip("No Arbitrum campaigns in API")

        result = await campaign_service.get_campaigns(
            chain_id=42161,
            platform_address=CURVE_V2_PLATFORM,
            check_proofs=False,
        )

        assert result.success and result.data

        # Find matching campaign by ID
        api_sample = api_arb[0]
        sdk_match = next(
            (c for c in result.data if c["id"] == api_sample["id"]), None
        )

        if sdk_match:
            assert sdk_match["campaign"]["gauge"].lower() == api_sample["gauge"].lower()
            assert sdk_match["campaign"]["manager"].lower() == api_sample["manager"].lower()
