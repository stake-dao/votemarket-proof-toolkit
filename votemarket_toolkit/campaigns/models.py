"""
Type definitions for VoteMarket campaigns.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, TypedDict

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
# TYPED DICTS (for JSON serialization)
# =============================================================================


class TokenInfoDict(TypedDict):
    """Token information dictionary for JSON serialization."""

    name: str
    symbol: str
    address: str
    decimals: int
    chain_id: int
    price: float


class PeriodDict(TypedDict, total=False):
    """Period information dictionary."""

    timestamp: int
    reward_per_period: int
    reward_per_vote: int
    leftover: int
    updated: bool
    point_data_inserted: bool
    block_updated: Optional[bool]


class CampaignDetailsDict(TypedDict):
    """Campaign details dictionary."""

    chain_id: int
    gauge: str
    manager: str
    reward_token: str
    number_of_periods: int
    max_reward_per_vote: int
    total_reward_amount: int
    total_distributed: int
    start_timestamp: int
    end_timestamp: int
    hook: str


class CampaignStatusInfoDict(TypedDict):
    """Campaign status dictionary."""

    status: str  # Will be CampaignStatus.value
    is_closed: bool
    can_close: bool
    who_can_close: str
    days_until_public_close: Optional[int]
    reason: str


class CampaignDict(TypedDict, total=False):
    """Complete campaign dictionary for JSON export."""

    # Required fields
    id: int
    campaign: CampaignDetailsDict
    is_closed: bool
    is_whitelist_only: bool
    addresses: List[str]

    # Optional fields
    current_epoch: Optional[int]
    remaining_periods: Optional[int]
    periods: Optional[List[PeriodDict]]
    status_info: Optional[CampaignStatusInfoDict]

    # Token information
    receipt_reward_token: Optional[TokenInfoDict]
    reward_token: Optional[TokenInfoDict]

    # Formatted dates
    formatted_start: Optional[str]
    formatted_end: Optional[str]


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
class TokenInfo:
    """Token information with metadata and pricing."""

    name: str  # Token name (e.g., "Curve DAO Token")
    symbol: str  # Token symbol (e.g., "CRV")
    address: str  # Token contract address
    decimals: int  # Token decimals (usually 18)
    chain_id: int  # Chain ID where token exists
    price: float  # Current USD price


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
    """
    Complete campaign data with token information.

    This represents a full campaign including on-chain data, calculated status,
    and enriched token information for LaPoste wrapped tokens.
    """

    # Core fields from contract
    id: int  # Campaign ID
    campaign: CampaignDetails  # Core campaign details
    is_closed: bool  # Whether campaign is closed
    is_whitelist_only: bool  # Whether whitelist is enabled
    addresses: List[str]  # Whitelisted addresses (if any)

    # Calculated fields
    current_epoch: Optional[int] = None  # Current epoch timestamp
    remaining_periods: Optional[int] = None  # Periods remaining
    periods: Optional[List[Period]] = None  # All period data
    status_info: Optional[CampaignStatusInfo] = None  # Calculated status info

    # Token information (LaPoste support)
    receipt_reward_token: Optional[TokenInfo] = (
        None  # LaPoste wrapped token (on-chain)
    )
    reward_token: Optional[TokenInfo] = None  # Native token (unwrapped)

    # Additional metadata for JSON export
    formatted_start: Optional[str] = None  # ISO format start date
    formatted_end: Optional[str] = None  # ISO format end date
