"""
Campaign optimization service for VoteMarket.

Calculates optimal campaign parameters based on:
- Historical gauge performance (EMA-smoothed)
- Current market rates (percentile-based, robust to outliers)
- Budget constraints
- Peer comparison
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional

from votemarket_toolkit.analytics.service import (
    AnalyticsService,
    get_analytics_service,
)
from votemarket_toolkit.analytics.statistics import (
    clamp,
    ema_series,
    mad,
    percentile,
    safe_divide,
)
from votemarket_toolkit.utils.pricing import get_erc20_prices_in_usd


@dataclass
class PeerFilters:
    """Filters for finding comparable peers in market data."""

    protocol: Optional[str] = None  # e.g., "curve"
    chain_id: Optional[int] = None  # e.g., 1 for Ethereum mainnet
    gauge_class: Optional[str] = None  # Future: gauge type classification


@dataclass
class OptimalCampaignResult:
    """Optimal campaign calculation result (simplified)."""

    # === CORE OUTPUTS ===
    max_reward_per_vote_tokens: float  # Max tokens/vote to set in contract
    max_reward_per_vote_usd: float  # Equivalent in USD
    tokens_needed: float  # Total tokens needed to achieve target
    duration_weeks: int  # Campaign duration

    # === BUDGET ANALYSIS ===
    total_budget: float  # Your input budget
    budget_surplus_pct: float  # % over-budgeted (0 if tight/under)
    budget_shortfall_pct: float  # % under-budgeted (0 if sufficient)

    # === EXPECTATIONS ===
    votes_expected: float  # Expected votes per period (EMA)
    efficiency_expected: float  # Expected efficiency % (EMA)

    # === MARKET CONTEXT ===
    token_price: float  # Current token price USD
    market_target_usd: float  # Robust market target (P70 + MAD)
    peer_median_usd: Optional[float]  # Peer median $/vote
    peer_count: int  # Number of comparable peers
    pct_above_peer_median: Optional[float]  # % above/below peer median

    # === HISTORICAL PERFORMANCE ===
    historical_dpv_usd: float  # Your historical $/vote (EMA)
    historical_votes: float  # Your historical votes (EMA)


class CampaignOptimizer:
    """
    Calculate optimal campaign parameters using robust statistics.

    Uses percentile-based targeting, EMA smoothing, and MAD margins
    for outlier-resistant market analysis.
    """

    def __init__(self, analytics_service: Optional[AnalyticsService] = None):
        self.analytics = analytics_service or get_analytics_service()

    async def calculate_optimal_campaign(
        self,
        protocol: str,
        gauge: str,
        reward_token: str,
        chain_id: int,
        total_reward_tokens: float,
        default_duration_weeks: int = 2,
        # Robust targeting parameters
        market_percentile: float = 0.70,  # Target 70th percentile
        ema_alpha: float = 0.3,  # EMA smoothing factor
        mad_multiplier: float = 0.5,  # MAD margin multiplier (k)
        min_ppv_usd: float = 0.0001,  # Minimum $/vote (clamp floor)
        max_ppv_usd: float = 1.0,  # Maximum $/vote (clamp ceiling)
        # Efficiency guardrail
        efficiency_floor: Optional[float] = None,  # e.g., 1.05 for +5% minimum
        # Peer filtering
        peer_filters: Optional[PeerFilters] = None,
    ) -> OptimalCampaignResult:
        """
        Calculate optimal campaign parameters using robust statistics.

        Args:
            protocol: Protocol name (e.g., "curve", "balancer")
            gauge: Gauge address
            reward_token: Reward token address
            chain_id: Chain ID for token pricing
            total_reward_tokens: Total tokens to distribute
            default_duration_weeks: Default duration
            market_percentile: Target market percentile (0.0-1.0, default 0.70)
            ema_alpha: EMA smoothing factor (0.0-1.0, default 0.3)
            mad_multiplier: MAD margin multiplier (default 0.5)
            min_ppv_usd: Minimum $/vote clamp (default 0.0001)
            max_ppv_usd: Maximum $/vote clamp (default 1.0)
            efficiency_floor: Minimum efficiency multiplier (e.g., 1.05 = +5%)
            peer_filters: Filters for comparable peer campaigns

        Returns:
            OptimalCampaignResult with all calculated parameters
        """
        if peer_filters is None:
            peer_filters = PeerFilters(protocol=protocol, chain_id=chain_id)

        # Fetch all data in parallel
        token_price_task = asyncio.create_task(
            self._fetch_token_price(chain_id, reward_token)
        )
        history_task = asyncio.create_task(
            self.analytics.fetch_gauge_history(protocol, gauge)
        )
        market_task = asyncio.create_task(
            self.analytics.get_current_market_snapshot(protocol, chain_id=None)
        )

        token_price, history, market_snapshot = await asyncio.gather(
            token_price_task, history_task, market_task
        )

        # Calculate EMA-smoothed historical metrics
        recent_rounds = history.get_recent_rounds(5)
        if not recent_rounds:
            raise ValueError(f"No historical data found for gauge {gauge}")

        dpv_series = [
            r.analytic.dollar_per_vote for r in reversed(recent_rounds)
        ]
        efficiency_series = [
            r.analytic.efficiency for r in reversed(recent_rounds)
        ]
        votes_series = [
            r.analytic.non_blacklisted_votes for r in reversed(recent_rounds)
        ]

        avg_dollar_per_vote = ema_series(dpv_series, alpha=ema_alpha)
        avg_efficiency = ema_series(efficiency_series, alpha=ema_alpha)
        votes_expected = ema_series(votes_series, alpha=ema_alpha)

        # Filter to comparable peer campaigns
        peer_campaigns = self._filter_peer_campaigns(
            market_snapshot, peer_filters, gauge
        )
        peer_dpv_values = [
            c["dollar_per_vote"]
            for c in peer_campaigns
            if c["dollar_per_vote"] > 0
        ]

        if not peer_dpv_values:
            peer_dpv_values = [
                c["dollar_per_vote"]
                for c in market_snapshot["campaigns"]
                if c["dollar_per_vote"] > 0
            ]

        # Calculate robust market target: percentile + MAD margin
        if peer_dpv_values:
            market_p = percentile(peer_dpv_values, market_percentile)
            market_mad = mad(peer_dpv_values)
            market_target_raw = market_p + mad_multiplier * market_mad
        else:
            market_target_raw = avg_dollar_per_vote

        market_percentile_target = clamp(
            market_target_raw, min_ppv_usd, max_ppv_usd
        )
        ppv_target_before_budget = market_percentile_target

        # Calculate campaign parameters from budget
        duration_weeks = default_duration_weeks
        reward_per_period_tokens = safe_divide(
            total_reward_tokens, duration_weeks
        )

        max_reward_per_vote_usd = ppv_target_before_budget
        max_reward_per_vote_tokens = safe_divide(
            max_reward_per_vote_usd, token_price
        )
        total_reward_per_period_tokens = (
            max_reward_per_vote_tokens * votes_expected
        )

        # Check budget sufficiency
        budget_shortfall_pct = 0.0
        budget_surplus_pct = 0.0

        if (
            reward_per_period_tokens < total_reward_per_period_tokens
            and votes_expected > 0
        ):
            shortfall = (
                total_reward_per_period_tokens - reward_per_period_tokens
            )
            budget_shortfall_pct = (
                safe_divide(shortfall, total_reward_per_period_tokens) * 100
            )

            max_reward_per_vote_tokens = safe_divide(
                reward_per_period_tokens, votes_expected
            )
            max_reward_per_vote_usd = max_reward_per_vote_tokens * token_price
        elif (
            reward_per_period_tokens > total_reward_per_period_tokens
            and votes_expected > 0
        ):
            surplus = reward_per_period_tokens - total_reward_per_period_tokens
            budget_surplus_pct = (
                safe_divide(surplus, reward_per_period_tokens) * 100
            )

        # Calculate market positioning
        peer_median = (
            percentile(peer_dpv_values, 0.5) if peer_dpv_values else None
        )
        pct_vs_peer = (
            safe_divide(max_reward_per_vote_usd - peer_median, peer_median)
            * 100
            if peer_median
            else None
        )

        # Calculate total tokens needed
        tokens_needed = total_reward_per_period_tokens * duration_weeks

        # Return simplified result
        return OptimalCampaignResult(
            # Core outputs
            max_reward_per_vote_tokens=max_reward_per_vote_tokens,
            max_reward_per_vote_usd=max_reward_per_vote_usd,
            tokens_needed=tokens_needed,
            duration_weeks=duration_weeks,
            # Budget analysis
            total_budget=total_reward_tokens,
            budget_surplus_pct=budget_surplus_pct,
            budget_shortfall_pct=budget_shortfall_pct,
            # Expectations
            votes_expected=votes_expected,
            efficiency_expected=avg_efficiency,
            # Market context
            token_price=token_price,
            market_target_usd=market_percentile_target,
            peer_median_usd=peer_median,
            peer_count=len(peer_dpv_values),
            pct_above_peer_median=pct_vs_peer,
            # Historical performance
            historical_dpv_usd=avg_dollar_per_vote,
            historical_votes=votes_expected,
        )

    async def _fetch_token_price(
        self, chain_id: int, reward_token: str
    ) -> float:
        """Fetch token price with error handling."""
        try:
            prices_result = get_erc20_prices_in_usd(
                chain_id, [(reward_token, 10**18)], timestamp=None
            )
            return prices_result[0][1] if prices_result else 0.0
        except Exception:
            return 0.0

    def _filter_peer_campaigns(
        self,
        market_snapshot: Dict,
        peer_filters: PeerFilters,
        exclude_gauge: str,
    ) -> List[Dict]:
        """Filter campaigns to find comparable peers."""
        # Start with all campaigns
        campaigns = market_snapshot.get("campaigns", [])

        # Filter by chain if specified
        if peer_filters.chain_id is not None:
            campaigns = [
                c
                for c in campaigns
                if c.get("chain_id") == peer_filters.chain_id
            ]

        # Exclude own gauge
        exclude_gauge_lower = exclude_gauge.lower()
        campaigns = [
            c
            for c in campaigns
            if c.get("gauge_address", "").lower() != exclude_gauge_lower
        ]

        # Future: could add gauge_class filtering here

        return campaigns

    async def close(self):
        """Close analytics service connection."""
        await self.analytics.close()


# Singleton instance
_optimizer_instance: Optional[CampaignOptimizer] = None


def get_campaign_optimizer() -> CampaignOptimizer:
    """Get singleton CampaignOptimizer instance."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = CampaignOptimizer()
    return _optimizer_instance
