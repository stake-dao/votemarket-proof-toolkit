"""
User Eligibility Service - Check user eligibility across VoteMarket campaigns

This service provides efficient checking of user eligibility by:
1. Processing multiple campaigns and periods in parallel
2. Filtering out closable campaigns automatically
3. Caching proof data to avoid redundant requests
4. Batching HTTP requests for optimal performance

The service is used by CLI commands, Streamlit UI, and can be imported in scripts.
"""

import asyncio
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, TypedDict

from eth_utils import to_checksum_address

from votemarket_toolkit.campaigns.models import CampaignStatus
from votemarket_toolkit.campaigns.service import CampaignService
from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.constants import GlobalConstants
from votemarket_toolkit.shared.logging import get_logger
from votemarket_toolkit.shared.services.http_client import get_async_client


class PeriodEligibilityResult(TypedDict):
    """Typed result for a single period eligibility check."""

    period: int
    epoch: int
    status: str
    has_proof: bool
    claimable: bool
    reason: str


class CampaignEligibilitySummary(TypedDict):
    total_periods: int
    claimable_periods: int
    has_eligibility: bool


class CampaignEligibilityResult(TypedDict):
    id: int
    gauge: str
    manager: str
    reward_token: str
    is_closed: bool
    periods: List[PeriodEligibilityResult]
    summary: CampaignEligibilitySummary


class UserEligibilityService:
    """Service for checking user eligibility with parallel processing."""

    # Base URLs
    PROOF_BASE_URL = (
        "https://raw.githubusercontent.com/stake-dao/api/main/api/votemarket"
    )
    GITHUB_API_BASE = (
        "https://api.github.com/repos/stake-dao/api/contents/api/votemarket"
    )

    # Concurrency limits
    MAX_CONCURRENT_REQUESTS = 50  # Process up to 50 requests in parallel

    def __init__(self):
        self.campaign_service = CampaignService()
        self._proof_cache: Dict[str, dict] = {}  # Cache proof data by URL
        self._directory_cache: Dict[
            str, Set[str]
        ] = {}  # Cache directory listings
        self._log = get_logger(__name__)

        # Allow tuning via env for easier ops/debugging
        try:
            max_conc = int(os.getenv("VM_MAX_CONCURRENCY", "0"))
            if max_conc > 0:
                self.MAX_CONCURRENT_REQUESTS = max_conc
        except ValueError:
            pass

        # Reuse shared AsyncClient for connection pooling
        self._client = get_async_client()

    async def _fetch_directory_structure(
        self, epoch: int, protocol: str
    ) -> Set[str]:
        """Fetch the directory structure for an epoch to know which proofs exist."""
        cache_key = f"{epoch}/{protocol}"
        if cache_key in self._directory_cache:
            return self._directory_cache[cache_key]

        # Try to get directory listing from GitHub API
        url = f"{self.GITHUB_API_BASE}/{epoch}/{protocol}"

        try:
            response = await self._client.get(url)
            if response.status_code == 200:
                data = response.json()
                # Extract all available proof paths
                proof_paths: Set[str] = set()
                for item in data:
                    if item.get("type") == "dir":
                        platform_path = item.get("path")
                        if platform_path:
                            proof_paths.add(platform_path)

                self._directory_cache[cache_key] = proof_paths
                return proof_paths
        except Exception as exc:
            self._log.debug(
                "Directory listing failed for %s: %s", cache_key, str(exc)
            )

        return set()

    async def _check_proof_batch(
        self, requests: List[Dict]
    ) -> List[PeriodEligibilityResult]:
        """Check multiple proofs in parallel."""
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        async def check_one(request: Dict) -> PeriodEligibilityResult:
            async with semaphore:
                period = request["period"]
                epoch = period["timestamp"]
                protocol = request["protocol"]
                platform_address = request["platform_address"]
                chain_id = request["chain_id"]
                gauge_address = request["gauge_address"]
                user_address = request["user_address"]

                # Build URL
                url = (
                    f"{self.PROOF_BASE_URL}/{epoch}/{protocol}/"
                    f"{platform_address.lower()}/{chain_id}/"
                    f"{gauge_address.lower()}.json"
                )

                # Check cache first
                proof_data = self._proof_cache.get(url)
                if proof_data is None:
                    try:
                        response = await self._client.get(url)
                        if response.status_code == 200:
                            proof_data = response.json()
                            self._proof_cache[url] = proof_data
                        else:
                            proof_data = None
                    except Exception as exc:
                        self._log.debug(
                            "Proof fetch failed %s: %s", url, str(exc)
                        )
                        proof_data = None

                # Build result
                result = {
                    "period": request["period_index"] + 1,
                    "epoch": epoch,
                    "status": request["period_status"],
                    "has_proof": False,
                    "claimable": False,
                    "reason": "Proofs not yet available",
                }

                if proof_data:
                    users = proof_data.get("users", {})
                    if isinstance(users, dict) and (
                        user_address.lower() in users
                    ):
                        result["has_proof"] = True
                        result["claimable"] = True
                        result["reason"] = "Ready to claim"
                    else:
                        result["reason"] = "No votes found for this period"

                return result

        # Process all requests in parallel
        tasks = [check_one(req) for req in requests]
        return await asyncio.gather(*tasks)

    async def check_campaigns_batch(
        self,
        campaigns: List[dict],
        user_address: str,
        protocol: str,
        chain_id: int,
        platform_address: str,
    ) -> List[CampaignEligibilityResult]:
        """Check eligibility for multiple campaigns in parallel."""
        current_time = int(datetime.now(timezone.utc).timestamp())
        eligible_campaigns = []

        # Prepare all requests
        all_requests = []
        campaign_request_map = defaultdict(
            list
        )  # Map campaign to its requests

        for campaign in campaigns:
            if not campaign.get("periods"):
                continue

            gauge_address = campaign["campaign"]["gauge"]

            for i, period in enumerate(campaign["periods"]):
                # Only check past/current periods
                if current_time >= period["timestamp"]:
                    period_status = (
                        "Active"
                        if current_time
                        < period["timestamp"] + GlobalConstants.WEEK
                        else "Ended"
                    )

                    request = {
                        "campaign": campaign,
                        "period": period,
                        "period_index": i,
                        "period_status": period_status,
                        "protocol": protocol,
                        "platform_address": platform_address,
                        "chain_id": chain_id,
                        "gauge_address": gauge_address,
                        "user_address": user_address,
                    }

                    all_requests.append(request)
                    campaign_request_map[campaign["id"]].append(
                        len(all_requests) - 1
                    )

        if not all_requests:
            return eligible_campaigns

        # Process all requests in parallel
        self._log.info(
            "Checking %d periods across %d campaigns in parallel...",
            len(all_requests),
            len(campaigns),
        )
        results = await self._check_proof_batch(all_requests)

        # Group results by campaign
        for campaign_id, request_indices in campaign_request_map.items():
            campaign = next(c for c in campaigns if c["id"] == campaign_id)
            periods_data = []
            has_any_proof = False
            claimable_count = 0

            # Add future periods first
            period_index = 0
            for period in campaign["periods"]:
                if current_time < period["timestamp"]:
                    periods_data.append(
                        {
                            "period": period_index + 1,
                            "epoch": period["timestamp"],
                            "status": "Future",
                            "has_proof": False,
                            "claimable": False,
                            "reason": "Period hasn't started yet",
                        }
                    )
                period_index += 1

            # Add checked periods
            for idx in request_indices:
                result = results[idx]
                periods_data.append(result)
                if result["has_proof"]:
                    has_any_proof = True
                if result["claimable"]:
                    claimable_count += 1

            # Only include campaigns where user has proofs
            if has_any_proof:
                eligible_campaigns.append(
                    {
                        "id": campaign["id"],
                        "gauge": campaign["campaign"]["gauge"],
                        "manager": campaign["campaign"]["manager"],
                        "reward_token": campaign["campaign"]["reward_token"],
                        "is_closed": campaign["is_closed"],
                        "periods": sorted(
                            periods_data, key=lambda x: x["period"]
                        ),
                        "summary": {
                            "total_periods": len(periods_data),
                            "claimable_periods": claimable_count,
                            "has_eligibility": has_any_proof,
                        },
                    }
                )

        return eligible_campaigns

    async def check_user_eligibility(
        self,
        user: str,
        protocol: str,
        chain_id: Optional[int] = None,
        gauge_address: Optional[str] = None,
        status_filter: str = "all",
    ) -> Dict:
        """
        Fast check of user eligibility using parallel processing.
        """
        user = to_checksum_address(user)
        protocol = protocol.lower()

        # Get platforms
        platforms = registry.get_all_platforms(protocol)
        if chain_id:
            platforms = [p for p in platforms if p["chain_id"] == chain_id]

        if not platforms:
            return {
                "user": user,
                "protocol": protocol,
                "summary": {
                    "total_campaigns_checked": 0,
                    "campaigns_with_eligibility": 0,
                    "total_claimable_periods": 0,
                },
                "chains": {},
            }

        # Results structure
        results = {
            "user": user,
            "protocol": protocol,
            "summary": {
                "total_campaigns_checked": 0,
                "campaigns_with_eligibility": 0,
                "total_claimable_periods": 0,
            },
            "chains": {},
        }

        # Process each platform
        for platform in platforms:
            chain_id = platform["chain_id"]
            platform_address = platform["address"]

            self._log.info(
                "Checking platform %s on chain %s...",
                platform_address,
                chain_id,
            )

            # Get campaigns
            try:
                # Use optimized method for active campaigns when appropriate
                if status_filter == "active" and not gauge_address:
                    campaigns = (
                        await self.campaign_service.get_active_campaigns(
                            chain_id=chain_id,
                            platform_address=platform_address,
                            check_proofs=False,
                        )
                    )
                else:
                    campaigns = await self.campaign_service.get_campaigns(
                        chain_id=chain_id,
                        platform_address=platform_address,
                        active_only=False,
                    )

                # Filter out closable campaigns (unless looking for closed)
                if status_filter != "closed":
                    filtered = []
                    for c in campaigns:
                        if c["is_closed"]:
                            if status_filter != "active":
                                filtered.append(c)
                        elif c.get("status_info", {}).get("status") not in [
                            CampaignStatus.CLOSABLE_BY_MANAGER.value,
                            CampaignStatus.CLOSABLE_BY_EVERYONE.value,
                        ]:
                            filtered.append(c)
                    campaigns = filtered

                if not campaigns:
                    continue

                # Filter by gauge if specified
                if gauge_address:
                    campaigns = [
                        c
                        for c in campaigns
                        if c["campaign"]["gauge"].lower()
                        == to_checksum_address(gauge_address).lower()
                    ]

                # Apply additional status filter
                if status_filter == "closed":
                    campaigns = [c for c in campaigns if c["is_closed"]]

                self._log.info(
                    "Found %d campaigns to check...", len(campaigns)
                )

                # Check eligibility for all campaigns in parallel
                eligible_campaigns = await self.check_campaigns_batch(
                    campaigns=campaigns,
                    user_address=user,
                    protocol=protocol,
                    chain_id=chain_id,
                    platform_address=platform_address,
                )

                # Update results
                results["summary"]["total_campaigns_checked"] += len(campaigns)

                if eligible_campaigns:
                    results["chains"][chain_id] = {
                        "campaigns": eligible_campaigns,
                        "summary": {
                            "total_campaigns": len(campaigns),
                            "eligible_campaigns": len(eligible_campaigns),
                            "claimable_periods": sum(
                                c["summary"]["claimable_periods"]
                                for c in eligible_campaigns
                            ),
                        },
                    }

                    results["summary"]["campaigns_with_eligibility"] += len(
                        eligible_campaigns
                    )
                    results["summary"]["total_claimable_periods"] += sum(
                        c["summary"]["claimable_periods"]
                        for c in eligible_campaigns
                    )

            except Exception as e:
                self._log.warning(
                    "Error processing chain %s: %s", chain_id, str(e)
                )
                continue

        return results

    async def close(self):
        """Cleanup method."""
        self._proof_cache.clear()
        self._directory_cache.clear()
        # Do not close the shared HTTP client here
        return None

    # Provide async context manager support for easier lifecycle handling
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
