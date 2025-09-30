"""
Campaign optimization service for VoteMarket.

WHAT THIS DOES:
Given your budget and gauge, calculates optimal campaign parameters:
1. Looks at historical performance (smoothed with EMA)
2. Checks current market rates (using percentiles to ignore outliers)
3. Calculates target $/vote with safety margin
4. Figures out max reward per vote that fits your budget

WHY THESE METHODS:
- Percentile (70th): Find typical market rate, not skewed by extremes
- EMA: Smooth historical data, giving more weight to recent trends
- MAD: Safety margin so you're competitive even if market shifts
- Clamp: Keep results within sensible min/max bounds
"""

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from votemarket_toolkit.analytics.service import AnalyticsService, get_analytics_service
from votemarket_toolkit.analytics.statistics import (
    percentile,
    ema_series,
    mad,
    clamp,
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
class CampaignParameters:
    """Calculated optimal campaign parameters."""

    # Target values
    ppv_target_before_budget: float  # Target $/vote before budget constraints
    ppv_target_after_budget: float  # Final $/vote after budget adjustment
    max_reward_per_vote_tokens: float  # Max tokens per vote
    max_reward_per_vote_usd: float  # Max $ per vote

    # Period parameters
    reward_per_period_tokens: float  # Tokens per period
    reward_per_period_usd: float  # USD per period
    duration_weeks: int  # Campaign duration
    period_distribution: List[float]  # Tokens per period

    # Vote expectations
    votes_expected: float  # EMA of historical votes

    # Budget analysis
    budget_shortfall_pct: float  # % shortfall if budget insufficient (0 if sufficient)

    # Efficiency
    projected_efficiency: float  # Expected efficiency %
    efficiency_floor_met: bool  # Whether efficiency floor is met

    # Warnings
    warnings: List[str]
    recommendations: List[str]


@dataclass
class MarketPositioning:
    """Market positioning analysis."""

    percentile: float  # Where you sit in the market (0-100, higher = more competitive)
    pct_vs_market_target: float  # % above/below market target
    pct_vs_peer_median: Optional[float]  # % above/below peer median
    is_above_market: bool
    peer_count: int  # Number of comparable peers


@dataclass
class OptimalCampaignResult:
    """Complete result of optimal campaign calculation."""

    # Core parameters
    parameters: CampaignParameters

    # Market positioning
    positioning: MarketPositioning

    # Input context
    total_reward_tokens: float
    token_price: float

    # Historical data (EMA smoothed)
    avg_dollar_per_vote: float  # EMA of historical $/vote
    avg_efficiency: float  # EMA of historical efficiency
    avg_votes: float  # EMA of historical votes

    # Market data
    market_percentile_target: float  # Robust market target (percentile + MAD)
    peer_median_dollar_per_vote: Optional[float]  # Peer median $/vote
    total_active_campaigns: int
    total_peer_campaigns: int  # Campaigns matching peer filters


class CampaignOptimizer:
    """
    Service for calculating optimal campaign parameters using robust statistics.

    Key features:
    - Percentile-based targeting (default: 70th percentile)
    - EMA smoothing for temporal stability
    - MAD margins for outlier protection
    - User-defined clamping policy
    - Efficiency guardrails
    - Parallel I/O for performance
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
        # Setup peer filters (compare to same chain by default)
        if peer_filters is None:
            peer_filters = PeerFilters(protocol=protocol, chain_id=chain_id)

        # ═══ STEP 1: Fetch all data in parallel (faster) ═══
        token_price_task = asyncio.create_task(self._fetch_token_price(chain_id, reward_token))
        history_task = asyncio.create_task(self.analytics.fetch_gauge_history(protocol, gauge))
        # Get market snapshot from ALL chains, we'll filter to peers after
        market_task = asyncio.create_task(
            self.analytics.get_current_market_snapshot(protocol, chain_id=None)
        )

        token_price, history, market_snapshot = await asyncio.gather(
            token_price_task, history_task, market_task
        )

        # ═══ STEP 2: Calculate smoothed historical averages ═══
        # Why EMA? Gives more weight to recent performance
        recent_rounds = history.get_recent_rounds(5)
        if not recent_rounds:
            raise ValueError(f"No historical data found for gauge {gauge}")

        # Extract time series (oldest to newest)
        dpv_series = [r.analytic.dollar_per_vote for r in reversed(recent_rounds)]
        efficiency_series = [r.analytic.efficiency for r in reversed(recent_rounds)]
        votes_series = [r.analytic.non_blacklisted_votes for r in reversed(recent_rounds)]

        # Smooth with EMA (alpha=0.3 means 30% weight to new, 70% to history)
        avg_dollar_per_vote = ema_series(dpv_series, alpha=ema_alpha)
        avg_efficiency = ema_series(efficiency_series, alpha=ema_alpha)
        votes_expected = ema_series(votes_series, alpha=ema_alpha)

        # ═══ STEP 3: Find comparable peer campaigns ═══
        # Only compare to same chain (e.g., Ethereum mainnet only)
        peer_campaigns = self._filter_peer_campaigns(market_snapshot, peer_filters, gauge)
        peer_dpv_values = [c["dollar_per_vote"] for c in peer_campaigns if c["dollar_per_vote"] > 0]

        if not peer_dpv_values:
            # No peers on same chain? Use all campaigns as fallback
            peer_dpv_values = [
                c["dollar_per_vote"]
                for c in market_snapshot["campaigns"]
                if c["dollar_per_vote"] > 0
            ]

        # ═══ STEP 4: Calculate target $/vote (robust method) ═══
        # Formula: target = percentile(70%) + safety_margin
        # Why? 70th percentile = typical competitive rate
        #      MAD margin = breathing room if market shifts
        if peer_dpv_values:
            market_p = percentile(peer_dpv_values, market_percentile)  # e.g., 70th percentile
            market_mad = mad(peer_dpv_values)  # Spread measure
            market_target_raw = market_p + mad_multiplier * market_mad  # Add safety margin
        else:
            # No market data: fall back to your historical average
            market_target_raw = avg_dollar_per_vote

        # Apply min/max bounds (sanity check)
        market_percentile_target = clamp(market_target_raw, min_ppv_usd, max_ppv_usd)

        # This is our target $/vote (before checking budget)
        ppv_target_before_budget = market_percentile_target

        # ═══ STEP 5: Calculate campaign parameters from your budget ═══
        duration_weeks = default_duration_weeks
        reward_per_period_tokens = safe_divide(total_reward_tokens, duration_weeks)
        reward_per_period_usd = reward_per_period_tokens * token_price

        # Convert $/vote target to tokens/vote
        max_reward_per_vote_usd = ppv_target_before_budget
        max_reward_per_vote_tokens = safe_divide(max_reward_per_vote_usd, token_price)

        # How many tokens needed per period to achieve target?
        # total_needed = max_tokens_per_vote * expected_votes
        total_reward_per_period_tokens = max_reward_per_vote_tokens * votes_expected

        # ═══ STEP 6: Budget reality check ═══
        # Do we have enough budget to hit our target?
        warnings = []
        recommendations = []
        budget_shortfall_pct = 0.0
        ppv_target_after_budget = ppv_target_before_budget

        if reward_per_period_tokens < total_reward_per_period_tokens and votes_expected > 0:
            # Not enough budget - need to lower target
            shortfall = total_reward_per_period_tokens - reward_per_period_tokens
            budget_shortfall_pct = safe_divide(shortfall, total_reward_per_period_tokens) * 100

            warnings.append(
                f"Budget shortfall: {budget_shortfall_pct:.1f}%. "
                f"Need {total_reward_per_period_tokens * duration_weeks:,.2f} tokens "
                f"to maintain target ${ppv_target_before_budget:.6f}/vote"
            )

            # Adjust down to fit budget (deterministic, single pass)
            max_reward_per_vote_tokens = safe_divide(reward_per_period_tokens, votes_expected)
            max_reward_per_vote_usd = max_reward_per_vote_tokens * token_price
            ppv_target_after_budget = max_reward_per_vote_usd

            recommendations.append(
                f"Adjusted target: ${ppv_target_after_budget:.6f}/vote to fit budget"
            )

        # Split budget evenly across weeks
        period_distribution = [reward_per_period_tokens] * duration_weeks

        # ═══ STEP 7: Efficiency check (optional) ═══
        # Use historical efficiency as baseline projection
        projected_efficiency = avg_efficiency
        efficiency_floor_met = True

        if efficiency_floor is not None:
            required_efficiency = efficiency_floor * 100  # Convert multiplier to %
            if projected_efficiency < required_efficiency:
                efficiency_floor_met = False
                warnings.append(
                    f"Projected efficiency ({projected_efficiency:.1f}%) "
                    f"below floor ({required_efficiency:.1f}%)"
                )
                recommendations.append(
                    "Consider: (1) Increase $/vote target, "
                    "(2) Reduce duration, or (3) Increase budget"
                )

        parameters = CampaignParameters(
            ppv_target_before_budget=ppv_target_before_budget,
            ppv_target_after_budget=ppv_target_after_budget,
            max_reward_per_vote_tokens=max_reward_per_vote_tokens,
            max_reward_per_vote_usd=max_reward_per_vote_usd,
            reward_per_period_tokens=reward_per_period_tokens,
            reward_per_period_usd=reward_per_period_usd,
            duration_weeks=duration_weeks,
            period_distribution=period_distribution,
            votes_expected=votes_expected,
            budget_shortfall_pct=budget_shortfall_pct,
            projected_efficiency=projected_efficiency,
            efficiency_floor_met=efficiency_floor_met,
            warnings=warnings,
            recommendations=recommendations,
        )

        # Market positioning analysis
        final_dpv = ppv_target_after_budget
        campaigns_below = sum(1 for dpv in peer_dpv_values if dpv < final_dpv)
        total_peer_campaigns = len(peer_dpv_values)

        percentile_pos = (
            safe_divide(campaigns_below, total_peer_campaigns) * 100
            if total_peer_campaigns > 0
            else 0
        )

        peer_median = percentile(peer_dpv_values, 0.5) if peer_dpv_values else None
        pct_vs_market = safe_divide(final_dpv - market_percentile_target, market_percentile_target) * 100
        pct_vs_peer = (
            safe_divide(final_dpv - peer_median, peer_median) * 100 if peer_median else None
        )

        positioning = MarketPositioning(
            percentile=100 - percentile_pos,  # Top X%
            pct_vs_market_target=pct_vs_market,
            pct_vs_peer_median=pct_vs_peer,
            is_above_market=final_dpv > market_percentile_target,
            peer_count=total_peer_campaigns,
        )

        return OptimalCampaignResult(
            parameters=parameters,
            positioning=positioning,
            total_reward_tokens=total_reward_tokens,
            token_price=token_price,
            avg_dollar_per_vote=avg_dollar_per_vote,
            avg_efficiency=avg_efficiency,
            avg_votes=votes_expected,
            market_percentile_target=market_percentile_target,
            peer_median_dollar_per_vote=peer_median,
            total_active_campaigns=market_snapshot["total_active_campaigns"],
            total_peer_campaigns=total_peer_campaigns,
        )

    async def _fetch_token_price(self, chain_id: int, reward_token: str) -> float:
        """Fetch token price with error handling."""
        try:
            prices_result = get_erc20_prices_in_usd(
                chain_id, [(reward_token, 10**18)], timestamp=None
            )
            return prices_result[0][1] if prices_result else 0.0
        except Exception:
            return 0.0

    def _filter_peer_campaigns(
        self, market_snapshot: Dict, peer_filters: PeerFilters, exclude_gauge: str
    ) -> List[Dict]:
        """Filter campaigns to find comparable peers."""
        # Start with all campaigns
        campaigns = market_snapshot.get("campaigns", [])

        # Filter by chain if specified
        if peer_filters.chain_id is not None:
            campaigns = [c for c in campaigns if c.get("chain_id") == peer_filters.chain_id]

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