""" Types for the project """

from typing import List, TypedDict, Dict, Any


class Campaign(TypedDict):
    id: int
    chain_id: int
    gauge: str
    blacklist: List[str]

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

class ProtocolData(TypedDict):
    protocol: str
    platforms: Dict[str, Dict[str, Any]]

class AllProtocolsData(TypedDict):
    protocols: Dict[str, ProtocolData]
