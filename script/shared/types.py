""" Types for the project """

from typing import Dict, List, TypedDict


class Campaign(TypedDict):
    id: int
    chain_id: int
    gauge: str
    listed_users: List[str]


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
