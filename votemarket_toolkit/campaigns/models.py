"""
Type definitions for VoteMarket campaigns.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

# =============================================================================
# ENUMS
# =============================================================================


class CampaignStatus(Enum):
    """Campaign status enumeration."""

    CLOSED = "closed"  # Campaign is closed
    ACTIVE = "active"  # Campaign is active with periods remaining
    NOT_CLOSABLE = "not_closable"  # In claim period (0-6 months after end)
    CLOSABLE_BY_MANAGER = (
        "closable_by_manager"  # Manager can close (6-7 months after end)
    )
    CLOSABLE_BY_EVERYONE = (
        "closable_by_everyone"  # Anyone can close (7+ months after end)
    )


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class Platform:
    """VoteMarket platform information."""

    protocol: str  # "curve", "balancer", "fxn", "pendle"
    chain_id: int  # 1, 42161, 10, 8453, 137
    address: str  # Platform contract address
    version: str  # "v1", "v2", "v2_old"


@dataclass
class Period:
    """Campaign period information."""

    timestamp: int  # Epoch timestamp
    reward_per_period: int  # Total rewards for this period (wei)
    reward_per_vote: int  # Reward per vote (wei)
    leftover: int  # Leftover rewards (wei)
    updated: bool  # Whether period has been updated
    point_data_inserted: bool  # Whether proofs have been inserted
    block_updated: Optional[bool] = None  # Whether block info has been updated


@dataclass
class CampaignDetails:
    """Core campaign details from contract."""

    chain_id: int  # Chain where gauge is deployed
    gauge: str  # Gauge address
    manager: str  # Campaign manager address
    reward_token: str  # Reward token address
    number_of_periods: int  # Number of periods in campaign
    max_reward_per_vote: int  # Maximum reward per vote (wei)
    total_reward_amount: int  # Total campaign rewards (wei)
    total_distributed: int  # Total distributed so far (wei)
    start_timestamp: int  # Campaign start timestamp
    end_timestamp: int  # Campaign end timestamp
    hook: str  # Hook contract address (if any)


@dataclass
class CampaignStatusInfo:
    """Campaign status information."""

    status: CampaignStatus
    is_closed: bool
    can_close: bool
    who_can_close: str  # "everyone", "manager_only", "no_one"
    days_until_public_close: Optional[int]  # Days until anyone can close
    reason: str  # Human readable explanation


@dataclass
class Campaign:
    """Campaign data from contract."""

    id: int  # Campaign ID
    campaign: CampaignDetails  # Core campaign details
    is_closed: bool  # Whether campaign is closed
    is_whitelist_only: bool  # Whether whitelist is enabled
    addresses: List[str]  # Whitelisted addresses (if any)
    current_epoch: Optional[int] = None  # Current epoch timestamp
    remaining_periods: Optional[int] = None  # Periods remaining
    periods: Optional[List[Period]] = None  # All period data
    status_info: Optional[CampaignStatusInfo] = None  # Calculated status info
