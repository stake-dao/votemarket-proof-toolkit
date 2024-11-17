from typing import Dict, TypedDict

from votemarket_toolkit.proofs.types import BlockInfo


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
