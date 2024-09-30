""" Types for the project """

from typing import TypedDict


class Campaign(TypedDict):
    id: int
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
    BlockNumber: int
    BlockHash: str
    BlockTimestamp: int
    RlpBlockHeader: str


class EligibleUser(TypedDict):
    user: str
    last_vote: int
    slope: int
    power: int
    end: int
