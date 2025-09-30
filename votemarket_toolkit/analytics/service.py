"""
AnalyticsService - Service for fetching VoteMarket analytics data

This service handles:
1. Fetching round metadata from GitHub repository
2. Fetching specific round data with all gauge analytics
3. Fetching historical data for specific gauges
4. Calculating performance metrics and trends
5. Caching to minimize network requests

Data Source:
GitHub: https://github.com/stake-dao/votemarket-analytics
Raw Base URL: https://raw.githubusercontent.com/stake-dao/votemarket-analytics/refs/heads/main/analytics/votemarket-analytics/

Available Protocols:
- curve
- balancer
- pancakeswap
- pendle
"""

import httpx
import time
from typing import Dict, List, Optional
from eth_utils import to_checksum_address

from votemarket_toolkit.analytics.models import (
    RoundMetadata,
    GaugeAnalytics,
    RoundAnalytics,
    GaugeRoundData,
    GaugeHistory,
    VoteBreakdown,
)
from votemarket_toolkit.campaigns.service import CampaignService
from votemarket_toolkit.campaigns.models import CampaignStatus
from votemarket_toolkit.utils.pricing import get_erc20_prices_in_usd


class AnalyticsService:
    """
    Service for fetching and analyzing VoteMarket analytics data.

    This service provides methods for accessing historical campaign
    performance data from the VoteMarket analytics GitHub repository.
    """

    BASE_URL = "https://raw.githubusercontent.com/stake-dao/votemarket-analytics/refs/heads/main/analytics/votemarket-analytics"

    def __init__(self):
        """Initialize the analytics service with caching."""
        self._cache: Dict[str, any] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_cache_key(self, *args) -> str:
        """Generate cache key from arguments."""
        return ":".join(str(arg) for arg in args)

    async def _fetch_json(self, url: str) -> dict:
        """
        Fetch JSON data from URL with caching.

        Args:
            url: Full URL to fetch

        Returns:
            Parsed JSON data

        Raises:
            httpx.HTTPError: If request fails
        """
        cache_key = url
        if cache_key in self._cache:
            return self._cache[cache_key]

        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        self._cache[cache_key] = data
        return data

    def _build_url(self, protocol: str, path: str) -> str:
        """
        Build full URL for analytics endpoint.

        Args:
            protocol: Protocol name (curve, balancer, etc.)
            path: Path after protocol (e.g., "rounds-metadata.json")

        Returns:
            Full URL string
        """
        return f"{self.BASE_URL}/{protocol.lower()}/{path}"

    async def fetch_rounds_metadata(
        self, protocol: str
    ) -> List[RoundMetadata]:
        """
        Fetch all round metadata for a protocol.

        Args:
            protocol: Protocol name (curve, balancer, pancakeswap, pendle)

        Returns:
            List of RoundMetadata objects sorted by round ID

        Example:
            >>> service = AnalyticsService()
            >>> rounds = await service.fetch_rounds_metadata("curve")
            >>> print(f"Latest round: {rounds[-1].id}")
        """
        url = self._build_url(protocol, "rounds-metadata.json")
        data = await self._fetch_json(url)

        rounds = [
            RoundMetadata(id=r["id"], end_voting=r["endVoting"]) for r in data
        ]

        return sorted(rounds, key=lambda r: r.id)

    async def fetch_round_data(
        self, protocol: str, round_id: int
    ) -> RoundAnalytics:
        """
        Fetch complete analytics data for a specific round.

        Args:
            protocol: Protocol name
            round_id: Round ID to fetch

        Returns:
            RoundAnalytics object with all gauge data

        Example:
            >>> service = AnalyticsService()
            >>> round_data = await service.fetch_round_data("curve", 210)
            >>> print(f"Total deposited: ${round_data.total_deposited_usd:.2f}")
        """
        url = self._build_url(protocol, f"{round_id}.json")
        data = await self._fetch_json(url)

        # Parse gauge analytics
        gauge_analytics = []
        for analytic_data in data.get("analytics", []):
            # Parse vote breakdowns if available
            breakdowns = None
            if "nonBlacklistedVotesBreakdowns" in analytic_data:
                breakdowns = [
                    VoteBreakdown(
                        key=b["key"],
                        non_blacklisted_votes=b["nonBlacklistedVotes"],
                    )
                    for b in analytic_data["nonBlacklistedVotesBreakdowns"]
                ]

            gauge_analytics.append(
                GaugeAnalytics(
                    gauge=to_checksum_address(analytic_data["gauge"]),
                    non_blacklisted_votes=analytic_data[
                        "nonBlacklistedVotes"
                    ],
                    total_deposited=analytic_data["totalDeposited"],
                    dollar_per_vote=analytic_data["dollarPerVote"],
                    incentive_directed=analytic_data["incentiveDirected"],
                    incentive_directed_usd=analytic_data[
                        "incentiveDirectedUSD"
                    ],
                    efficiency=analytic_data["efficiency"],
                    platform=analytic_data.get("platform", "votemarket"),
                    non_blacklisted_votes_breakdowns=breakdowns,
                )
            )

        return RoundAnalytics(
            round_id=round_id,
            total_deposited_usd=data["totalDepositedUSD"],
            global_average_dollar_per_vote=data[
                "globalAverageDollarPerVote"
            ],
            global_average_efficiency=data["globalAverageEfficiency"],
            analytics=gauge_analytics,
        )

    async def fetch_gauge_history(
        self, protocol: str, gauge_address: str
    ) -> GaugeHistory:
        """
        Fetch complete historical data for a specific gauge.

        Args:
            protocol: Protocol name
            gauge_address: Gauge contract address

        Returns:
            GaugeHistory object with all historical rounds

        Example:
            >>> service = AnalyticsService()
            >>> history = await service.fetch_gauge_history(
            ...     "curve",
            ...     "0x0148ac2d0ffabb7634ffac5e7b770a34773e92ed"
            ... )
            >>> avg_dollar_per_vote = history.calculate_average_dollar_per_vote(3)
            >>> print(f"Avg $/vote (last 3 rounds): ${avg_dollar_per_vote:.4f}")
        """
        gauge_address = gauge_address.lower()
        url = self._build_url(protocol, f"gauges/{gauge_address}.json")

        # Fetch data - this is an array of round data points
        data = await self._fetch_json(url)

        # Parse each round data point
        history_data = []
        for round_data in data:
            round_details = round_data["roundDetails"]
            analytic_data = round_data["analytic"]

            # Parse vote breakdowns if available
            breakdowns = None
            if "nonBlacklistedVotesBreakdowns" in analytic_data:
                breakdowns = [
                    VoteBreakdown(
                        key=b["key"],
                        non_blacklisted_votes=b["nonBlacklistedVotes"],
                    )
                    for b in analytic_data["nonBlacklistedVotesBreakdowns"]
                ]

            # Use gauge from analytic data if present, otherwise use from URL
            gauge_addr = analytic_data.get(
                "gauge", to_checksum_address(gauge_address)
            )

            gauge_analytics = GaugeAnalytics(
                gauge=to_checksum_address(gauge_addr),
                non_blacklisted_votes=analytic_data["nonBlacklistedVotes"],
                total_deposited=analytic_data["totalDeposited"],
                dollar_per_vote=analytic_data["dollarPerVote"],
                incentive_directed=analytic_data["incentiveDirected"],
                incentive_directed_usd=analytic_data["incentiveDirectedUSD"],
                efficiency=analytic_data["efficiency"],
                platform=analytic_data.get("platform", "votemarket"),
                non_blacklisted_votes_breakdowns=breakdowns,
            )

            history_data.append(
                GaugeRoundData(
                    round_id=round_details["id"],
                    start_timestamp=round_details["startTimestamp"],
                    end_timestamp=round_details["endTimestamp"],
                    analytic=gauge_analytics,
                )
            )

        return GaugeHistory(
            gauge=to_checksum_address(gauge_address),
            protocol=protocol,
            history=history_data,
        )

    async def get_recent_rounds(
        self, protocol: str, n: int = 5
    ) -> List[RoundMetadata]:
        """
        Get the N most recent rounds for a protocol.

        Args:
            protocol: Protocol name
            n: Number of recent rounds to return (default: 5)

        Returns:
            List of RoundMetadata objects, most recent first

        Example:
            >>> service = AnalyticsService()
            >>> recent = await service.get_recent_rounds("curve", 3)
            >>> for round in recent:
            ...     print(f"Round {round.id}: {round.end_voting}")
        """
        all_rounds = await self.fetch_rounds_metadata(protocol)
        return sorted(all_rounds, key=lambda r: r.id, reverse=True)[:n]

    async def get_latest_round_id(self, protocol: str) -> int:
        """
        Get the latest round ID for a protocol.

        Args:
            protocol: Protocol name

        Returns:
            Latest round ID

        Example:
            >>> service = AnalyticsService()
            >>> latest = await service.get_latest_round_id("curve")
            >>> print(f"Latest round: {latest}")
        """
        recent = await self.get_recent_rounds(protocol, n=1)
        return recent[0].id if recent else 0

    async def calculate_gauge_metrics(
        self, protocol: str, gauge_address: str, n_rounds: int = 3
    ) -> Dict[str, float]:
        """
        Calculate average metrics for a gauge over recent rounds.

        Args:
            protocol: Protocol name
            gauge_address: Gauge contract address
            n_rounds: Number of recent rounds to average (default: 3)

        Returns:
            Dict with averaged metrics:
            - avg_dollar_per_vote: Average $/vote
            - avg_efficiency: Average efficiency
            - avg_total_deposited: Average total deposited
            - avg_votes: Average non-blacklisted votes

        Example:
            >>> service = AnalyticsService()
            >>> metrics = await service.calculate_gauge_metrics(
            ...     "curve",
            ...     "0x0148ac2d0ffabb7634ffac5e7b770a34773e92ed",
            ...     n_rounds=5
            ... )
            >>> print(f"Avg $/vote: ${metrics['avg_dollar_per_vote']:.4f}")
        """
        history = await self.fetch_gauge_history(protocol, gauge_address)
        recent = history.get_recent_rounds(n_rounds)

        if not recent:
            return {
                "avg_dollar_per_vote": 0.0,
                "avg_efficiency": 0.0,
                "avg_total_deposited": 0.0,
                "avg_votes": 0.0,
            }

        total_dpv = sum(r.analytic.dollar_per_vote for r in recent)
        total_eff = sum(r.analytic.efficiency for r in recent)
        total_dep = sum(r.analytic.total_deposited for r in recent)
        total_votes = sum(r.analytic.non_blacklisted_votes for r in recent)

        count = len(recent)

        return {
            "avg_dollar_per_vote": total_dpv / count,
            "avg_efficiency": total_eff / count,
            "avg_total_deposited": total_dep / count,
            "avg_votes": total_votes / count,
        }

    async def get_gauge_for_round(
        self, protocol: str, round_id: int, gauge_address: str
    ) -> Optional[GaugeAnalytics]:
        """
        Get analytics for a specific gauge in a specific round.

        Args:
            protocol: Protocol name
            round_id: Round ID
            gauge_address: Gauge contract address

        Returns:
            GaugeAnalytics object if found, None otherwise

        Example:
            >>> service = AnalyticsService()
            >>> gauge = await service.get_gauge_for_round(
            ...     "curve", 210, "0x0148ac2d0ffabb7634ffac5e7b770a34773e92ed"
            ... )
            >>> if gauge:
            ...     print(f"$/vote: ${gauge.dollar_per_vote:.4f}")
        """
        round_data = await self.fetch_round_data(protocol, round_id)
        gauge_address_checksummed = to_checksum_address(gauge_address)

        for gauge in round_data.analytics:
            if gauge.gauge == gauge_address_checksummed:
                return gauge

        return None

    async def get_current_market_snapshot(
        self,
        protocol: str,
        chain_id: Optional[int] = None,
        platform_address: Optional[str] = None,
    ) -> Dict:
        """
        Get current market snapshot of all active campaigns with live $/vote data.

        This fetches on-chain campaign data (not yet in analytics) to provide
        real-time market intelligence for competitive positioning.

        Args:
            protocol: Protocol name (curve, balancer, etc.)
            chain_id: Chain ID to query (optional, queries ALL chains if None)
            platform_address: Specific platform address (optional, uses latest if None)

        Returns:
            Dict with market statistics:
            - timestamp: Current timestamp
            - protocol: Protocol name
            - chain_ids: List of chain IDs queried
            - total_active_campaigns: Number of active campaigns
            - global_average_dollar_per_vote: Market avg $/vote
            - median_dollar_per_vote: Market median $/vote
            - min_dollar_per_vote: Minimum $/vote
            - max_dollar_per_vote: Maximum $/vote
            - campaigns: List of campaign data with $/vote
            - by_gauge: Campaigns grouped by gauge address
            - by_chain: Campaigns grouped by chain ID

        Example:
            >>> service = AnalyticsService()
            >>> # Get all chains
            >>> snapshot = await service.get_current_market_snapshot("curve")
            >>> print(f"Market avg: ${snapshot['global_average_dollar_per_vote']:.4f}/vote")
            >>> print(f"Active campaigns: {snapshot['total_active_campaigns']}")
            >>> # Get specific chain
            >>> snapshot = await service.get_current_market_snapshot("curve", 42161)
        """
        campaign_service = CampaignService()

        # Determine which platforms to query
        platforms_to_query = []

        if platform_address and chain_id:
            # Single specific platform
            platforms_to_query.append((chain_id, platform_address))
        elif chain_id:
            # All platforms on specific chain
            all_platforms = campaign_service.get_all_platforms(protocol)
            chain_platforms = [p for p in all_platforms if p.chain_id == chain_id]
            if not chain_platforms:
                raise ValueError(
                    f"No platform found for protocol {protocol} on chain {chain_id}"
                )
            # Prefer v2 over v2_old over v1
            version_priority = {"v2": 3, "v2_old": 2, "v1": 1}
            chain_platforms.sort(
                key=lambda p: version_priority.get(p.version, 0), reverse=True
            )
            platforms_to_query.append((chain_id, chain_platforms[0].address))
        else:
            # ALL platforms across ALL chains
            all_platforms = campaign_service.get_all_platforms(protocol)
            # Group by chain and take latest version per chain
            by_chain = {}
            for p in all_platforms:
                if p.chain_id not in by_chain:
                    by_chain[p.chain_id] = []
                by_chain[p.chain_id].append(p)

            # Take latest version per chain
            version_priority = {"v2": 3, "v2_old": 2, "v1": 1}
            for cid, chain_platforms in by_chain.items():
                chain_platforms.sort(
                    key=lambda p: version_priority.get(p.version, 0), reverse=True
                )
                platforms_to_query.append((cid, chain_platforms[0].address))

        # Fetch campaigns from all platforms concurrently
        async def fetch_platform_campaigns(chain_id: int, platform: str):
            try:
                return (chain_id, platform, await campaign_service.get_campaigns(
                    chain_id=chain_id,
                    platform_address=platform,
                    check_proofs=False,
                ))
            except Exception as e:
                print(f"Warning: Failed to fetch campaigns for chain {chain_id}: {e}")
                return (chain_id, platform, [])

        import asyncio
        results = await asyncio.gather(*[
            fetch_platform_campaigns(cid, platform)
            for cid, platform in platforms_to_query
        ])

        # Aggregate all campaigns
        all_campaigns = []
        for cid, platform, campaigns in results:
            all_campaigns.extend([(cid, platform, c) for c in campaigns])

        # Filter for active campaigns (not closed, has remaining periods or not ended)
        active_campaigns = []
        for cid, platform, campaign in all_campaigns:
            # Include if not closed AND has remaining periods
            is_closed = campaign.get("is_closed", False)
            remaining_periods = campaign.get("remaining_periods", 0)

            # Also check timestamp-based status
            current_timestamp = int(time.time())
            end_timestamp = campaign.get("campaign", {}).get("end_timestamp", 0)

            # Active if: not closed AND (has remaining periods OR hasn't ended yet)
            if not is_closed and (remaining_periods > 0 or end_timestamp >= current_timestamp):
                active_campaigns.append((cid, platform, campaign))

        if not active_campaigns:
            chain_ids = [cid for cid, _ in platforms_to_query]
            return {
                "timestamp": int(time.time()),
                "protocol": protocol,
                "chain_ids": chain_ids,
                "total_active_campaigns": 0,
                "global_average_dollar_per_vote": 0.0,
                "median_dollar_per_vote": 0.0,
                "min_dollar_per_vote": 0.0,
                "max_dollar_per_vote": 0.0,
                "campaigns": [],
                "by_gauge": {},
                "by_chain": {},
            }

        # Collect unique tokens per chain for batch price fetching
        tokens_by_chain = {}
        for cid, platform, campaign in active_campaigns:
            reward_token = campaign["campaign"].get("reward_token")
            if reward_token:
                if cid not in tokens_by_chain:
                    tokens_by_chain[cid] = set()
                tokens_by_chain[cid].add(reward_token.lower())

        # Fetch token prices in batch per chain
        token_price_cache = {}
        for cid, unique_tokens in tokens_by_chain.items():
            if unique_tokens:
                token_list = [(token, 10**18) for token in unique_tokens]
                try:
                    prices_result = get_erc20_prices_in_usd(
                        cid, token_list, timestamp=None
                    )
                    for token, (_, price_float) in zip(unique_tokens, prices_result):
                        cache_key = f"{cid}:{token.lower()}"
                        token_price_cache[cache_key] = price_float
                except Exception as e:
                    print(f"Warning: Failed to fetch prices for chain {cid}: {e}")

        # Calculate $/vote for each campaign
        campaign_data = []
        dollar_per_vote_list = []

        for cid, platform, campaign in active_campaigns:
            c = campaign["campaign"]
            reward_token = c.get("reward_token", "").lower()
            cache_key = f"{cid}:{reward_token}"
            token_price = token_price_cache.get(cache_key, 0.0)

            # Get current period's reward_per_vote
            periods = campaign.get("periods", [])
            current_period_index = c.get(
                "number_of_periods", 0
            ) - campaign.get("remaining_periods", 0)

            reward_per_vote = 0
            if periods and current_period_index < len(periods):
                current_period = periods[current_period_index]
                reward_per_vote = current_period.get("reward_per_vote", 0)

            # Get max_reward_per_vote cap
            max_reward_per_vote = c.get("max_reward_per_vote", 0)

            # Calculate $/vote respecting the max cap
            # Per Stake DAO docs: min(reward_per_vote, max_reward_per_vote)
            reward_per_vote_tokens = reward_per_vote / 10**18
            max_reward_per_vote_tokens = max_reward_per_vote / 10**18

            # Apply cap if max is set
            if max_reward_per_vote > 0:
                effective_reward_per_vote = min(
                    reward_per_vote_tokens, max_reward_per_vote_tokens
                )
            else:
                effective_reward_per_vote = reward_per_vote_tokens

            dollar_per_vote = effective_reward_per_vote * token_price

            # Calculate total remaining rewards
            total_remaining = sum(
                p.get("reward_per_period", 0)
                for p in periods[current_period_index:]
            )

            campaign_entry = {
                "campaign_id": campaign["id"],
                "chain_id": cid,
                "platform": platform,
                "gauge": c["gauge"],
                "reward_token": c["reward_token"],
                "reward_per_vote": effective_reward_per_vote,
                "max_reward_per_vote": max_reward_per_vote_tokens,
                "dollar_per_vote": dollar_per_vote,
                "total_remaining_rewards": total_remaining / 10**18,
                "remaining_periods": campaign.get("remaining_periods", 0),
                "token_price_usd": token_price,
            }

            campaign_data.append(campaign_entry)
            if dollar_per_vote > 0:
                dollar_per_vote_list.append(dollar_per_vote)

        # Calculate statistics
        global_avg = (
            sum(dollar_per_vote_list) / len(dollar_per_vote_list)
            if dollar_per_vote_list
            else 0.0
        )

        sorted_dpv = sorted(dollar_per_vote_list)
        median_dpv = (
            sorted_dpv[len(sorted_dpv) // 2] if sorted_dpv else 0.0
        )
        min_dpv = min(dollar_per_vote_list) if dollar_per_vote_list else 0.0
        max_dpv = max(dollar_per_vote_list) if dollar_per_vote_list else 0.0

        # Group by gauge
        by_gauge = {}
        for campaign_entry in campaign_data:
            gauge = campaign_entry["gauge"]
            if gauge not in by_gauge:
                by_gauge[gauge] = {
                    "campaigns": [],
                    "total_competitors": 0,
                    "avg_dollar_per_vote": 0.0,
                }

            by_gauge[gauge]["campaigns"].append(campaign_entry)
            by_gauge[gauge]["total_competitors"] += 1

        # Calculate per-gauge averages
        for gauge, data in by_gauge.items():
            gauge_dpv_list = [
                c["dollar_per_vote"]
                for c in data["campaigns"]
                if c["dollar_per_vote"] > 0
            ]
            data["avg_dollar_per_vote"] = (
                sum(gauge_dpv_list) / len(gauge_dpv_list)
                if gauge_dpv_list
                else 0.0
            )

        # Group by chain
        by_chain = {}
        for campaign_entry in campaign_data:
            cid = campaign_entry["chain_id"]
            if cid not in by_chain:
                by_chain[cid] = {
                    "campaigns": [],
                    "total_campaigns": 0,
                    "avg_dollar_per_vote": 0.0,
                }

            by_chain[cid]["campaigns"].append(campaign_entry)
            by_chain[cid]["total_campaigns"] += 1

        # Calculate per-chain averages
        for cid, data in by_chain.items():
            chain_dpv_list = [
                c["dollar_per_vote"]
                for c in data["campaigns"]
                if c["dollar_per_vote"] > 0
            ]
            data["avg_dollar_per_vote"] = (
                sum(chain_dpv_list) / len(chain_dpv_list)
                if chain_dpv_list
                else 0.0
            )

        chain_ids = [cid for cid, _ in platforms_to_query]

        # Calculate percentiles for strategy recommendations
        percentile_25 = (
            sorted_dpv[len(sorted_dpv) // 4] if sorted_dpv else 0.0
        )
        percentile_75 = (
            sorted_dpv[3 * len(sorted_dpv) // 4] if sorted_dpv else 0.0
        )

        return {
            "timestamp": int(time.time()),
            "protocol": protocol,
            "chain_ids": chain_ids,
            "total_active_campaigns": len(active_campaigns),
            "global_average_dollar_per_vote": global_avg,
            "median_dollar_per_vote": median_dpv,
            "percentile_25_dollar_per_vote": percentile_25,
            "percentile_75_dollar_per_vote": percentile_75,
            "min_dollar_per_vote": min_dpv,
            "max_dollar_per_vote": max_dpv,
            "campaigns": campaign_data,
            "by_gauge": by_gauge,
            "by_chain": by_chain,
        }


# Singleton instance
_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    """
    Get the singleton analytics service instance.

    Returns:
        AnalyticsService instance
    """
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service