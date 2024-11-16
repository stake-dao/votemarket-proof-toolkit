from typing import TypedDict


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
