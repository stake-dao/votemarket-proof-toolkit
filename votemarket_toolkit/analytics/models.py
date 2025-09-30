"""
Type definitions for VoteMarket analytics data.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class RoundMetadata:
    """Metadata for a VoteMarket round."""

    id: int  # Round ID
    end_voting: int  # Unix timestamp when voting ends


@dataclass
class VoteBreakdown:
    """Breakdown of votes by address/key."""

    key: str  # Address or identifier
    non_blacklisted_votes: float  # Vote amount


@dataclass
class GaugeAnalytics:
    """
    Analytics data for a specific gauge in a round.

    This represents the performance metrics of a gauge during
    a specific voting round, including deposits, votes, and efficiency.
    """

    gauge: str  # Gauge address
    non_blacklisted_votes: float  # Total non-blacklisted votes
    total_deposited: float  # Total incentives deposited (in token units)
    dollar_per_vote: float  # USD cost per vote
    incentive_directed: float  # Amount of incentive directed (in token units)
    incentive_directed_usd: float  # USD value of incentive directed
    efficiency: float  # Efficiency metric
    platform: str  # Platform name (e.g., "votemarket")
    non_blacklisted_votes_breakdowns: Optional[List[VoteBreakdown]] = (
        None  # Detailed vote breakdowns
    )


@dataclass
class RoundAnalytics:
    """
    Complete analytics data for a round across all gauges.

    This includes global metrics and individual gauge performance.
    """

    round_id: int  # Round ID
    total_deposited_usd: float  # Total USD deposited across all gauges
    global_average_dollar_per_vote: float  # Global average $/vote
    global_average_efficiency: float  # Global average efficiency
    analytics: List[GaugeAnalytics]  # Analytics for each gauge


@dataclass
class GaugeRoundData:
    """
    Single round data point for a gauge's history.

    Contains the round details and the gauge's performance in that round.
    """

    round_id: int  # Round ID
    start_timestamp: int  # Round start timestamp
    end_timestamp: int  # Round end timestamp
    analytic: GaugeAnalytics  # Gauge analytics for this round


@dataclass
class GaugeHistory:
    """
    Complete historical analytics for a specific gauge.

    This contains all round data for a gauge, allowing for
    historical analysis and trend calculation.
    """

    gauge: str  # Gauge address
    protocol: str  # Protocol (e.g., "curve", "balancer")
    history: List[GaugeRoundData]  # Historical data points

    def get_recent_rounds(self, n: int = 5) -> List[GaugeRoundData]:
        """Get the N most recent rounds."""
        return sorted(self.history, key=lambda x: x.round_id, reverse=True)[
            :n
        ]

    def calculate_average_dollar_per_vote(self, n_rounds: int = 3) -> float:
        """
        Calculate average dollar per vote over the last N rounds.

        Args:
            n_rounds: Number of recent rounds to average (default: 3)

        Returns:
            Average $/vote, or 0.0 if no data available
        """
        recent = self.get_recent_rounds(n_rounds)
        if not recent:
            return 0.0

        valid_rounds = [
            r.analytic.dollar_per_vote
            for r in recent
            if r.analytic.dollar_per_vote > 0
        ]

        return sum(valid_rounds) / len(valid_rounds) if valid_rounds else 0.0

    def calculate_average_efficiency(self, n_rounds: int = 3) -> float:
        """
        Calculate average efficiency over the last N rounds.

        Args:
            n_rounds: Number of recent rounds to average (default: 3)

        Returns:
            Average efficiency, or 0.0 if no data available
        """
        recent = self.get_recent_rounds(n_rounds)
        if not recent:
            return 0.0

        valid_rounds = [
            r.analytic.efficiency
            for r in recent
            if r.analytic.efficiency > 0
        ]

        return sum(valid_rounds) / len(valid_rounds) if valid_rounds else 0.0

    def get_total_votes_by_round(self) -> Dict[int, float]:
        """
        Get total non-blacklisted votes by round ID.

        Returns:
            Dict mapping round_id to total votes
        """
        return {
            r.round_id: r.analytic.non_blacklisted_votes for r in self.history
        }

    def get_total_deposited_by_round(self) -> Dict[int, float]:
        """
        Get total deposited by round ID.

        Returns:
            Dict mapping round_id to total deposited
        """
        return {
            r.round_id: r.analytic.total_deposited for r in self.history
        }