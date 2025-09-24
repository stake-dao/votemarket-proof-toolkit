from typing import Dict, List, Optional, TypedDict


class Platform(TypedDict):
    protocol: str
    chain_id: int
    address: str


class Period(TypedDict):
    timestamp: int
    reward_per_period: int
    reward_per_vote: int
    leftover: int
    updated: bool
    point_data_inserted: bool



class CampaignDetails(TypedDict):
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


class Campaign(TypedDict):
    id: int
    chain_id: int
    gauge: str
    manager: str
    reward_token: str
    is_closed: bool
    is_whitelist_only: bool
    listed_users: List[str]
    period_left: int
    details: CampaignDetails
    periods : List[Period]


class CampaignData(TypedDict):
    """Raw campaign data from contract"""

    id: int
    campaign: CampaignDetails
    is_closed: bool
    is_whitelist_only: bool
    addresses: List[str]
    current_period: Period
    period_left: int
