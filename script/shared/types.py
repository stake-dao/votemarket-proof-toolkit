""" Types for the project """

from typing import Dict, List, TypedDict


class Period(TypedDict):
    reward_per_period: int
    reward_per_vote: int
    leftover: int
    updated: bool


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
    current_period: Period


class CampaignData(TypedDict):
    """Raw campaign data from contract"""

    id: int
    campaign: CampaignDetails
    is_closed: bool
    is_whitelist_only: bool
    addresses: List[str]
    current_period: Period
    period_left: int


class Platform(TypedDict):
    protocol: str
    chain_id: int
    address: str


class UserProof(TypedDict):
    account_proof: bytes
    storage_proof: bytes


class GaugeProof(TypedDict):
    gauge_controller_proof: bytes
    point_data_proof: bytes


class BlockInfo(TypedDict):
    block_number: int
    block_hash: str
    block_timestamp: int
    rlp_block_header: str


class EligibleUser(TypedDict):
    user: str
    last_vote: int
    slope: int
    power: int
    end: int


class PlatformData(TypedDict):
    address: str
    latest_setted_block: int
    block_data: BlockInfo
    oracle_address: str
    lens_address: str


class ProtocolData(TypedDict):
    platforms: Dict[int, PlatformData]  # Chain id -> Platform data


class AllProtocolsData(TypedDict):
    protocols: Dict[str, ProtocolData]
