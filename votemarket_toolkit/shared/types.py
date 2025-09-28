"""
Shared type definitions used across the VoteMarket toolkit.
"""

from typing import Dict, TypedDict

from votemarket_toolkit.proofs.types import BlockInfo

# =============================================================================
# USER TYPES
# =============================================================================


class EligibleUser(TypedDict):
    """User eligible for voting with their vote details."""

    user: str  # User address
    last_vote: int  # Last vote timestamp
    slope: int  # Vote slope
    power: int  # Voting power
    end: int  # Vote end timestamp


# =============================================================================
# PLATFORM & PROTOCOL TYPES
# =============================================================================


class PlatformData(TypedDict):
    """VoteMarket platform data with oracle information."""

    address: str  # Platform contract address
    latest_setted_block: int  # Latest block number set
    block_data: BlockInfo  # Block information
    oracle_address: str  # Oracle contract address
    lens_address: str  # Oracle lens contract address


class ProtocolData(TypedDict):
    """Protocol data containing all platforms across chains."""

    platforms: Dict[int, PlatformData]  # Chain ID -> Platform data


class AllProtocolsData(TypedDict):
    """Container for all protocols data."""

    protocols: Dict[str, ProtocolData]  # Protocol name -> Protocol data
