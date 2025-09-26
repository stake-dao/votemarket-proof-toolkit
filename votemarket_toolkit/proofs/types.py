"""
Type definitions for VoteMarket proofs.
"""

from typing import TypedDict


# =============================================================================
# PROOF TYPES
# =============================================================================


class UserProof(TypedDict):
    """Merkle proof for user voting data."""

    account_proof: bytes  # Account proof in state trie
    storage_proof: bytes  # Storage proof for user data


class GaugeProof(TypedDict):
    """Merkle proof for gauge voting data."""

    gauge_controller_proof: bytes  # Proof in gauge controller
    point_data_proof: bytes  # Proof for point data


# =============================================================================
# BLOCK TYPES
# =============================================================================


class BlockInfo(TypedDict):
    """Ethereum block information for proof verification."""

    block_number: int  # Block number
    block_hash: str  # Block hash (hex string)
    block_timestamp: int  # Block timestamp
    rlp_block_header: str  # RLP encoded block header
