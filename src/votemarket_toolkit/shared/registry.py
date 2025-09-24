"""
Simplified registry for all VoteMarket addresses and configuration.
Single source of truth for the entire toolkit.
"""

from typing import Dict, List, Optional


# =============================================================================
# VOTEMARKET PLATFORM ADDRESSES
# =============================================================================

VOTEMARKET_PLATFORMS = {
    "curve": {
        "v1": {
            42161: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",  # Arbitrum
            10: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",  # Optimism
            8453: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",  # Base
            137: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",  # Polygon
        },
        "v2": {
            42161: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",  # Arbitrum
            10: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",  # Optimism
            8453: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",  # Base
            137: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",  # Polygon
        },
    },
    "balancer": {
        "v1": {
            42161: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",  # Arbitrum
            10: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",  # Optimism
            8453: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",  # Base
            137: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",  # Polygon
        },
    },
    "fxn": {
        "v1": {
            42161: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",  # Arbitrum
            10: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",  # Optimism
            8453: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",  # Base
            137: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",  # Polygon
        },
    },
    "pendle": {
        "v1": {
            42161: "0x105694FC5204787eD571842671d1262A54a8135B",  # Arbitrum
            10: "0x105694FC5204787eD571842671d1262A54a8135B",  # Optimism
            8453: "0x105694FC5204787eD571842671d1262A54a8135B",  # Base
            137: "0x105694FC5204787eD571842671d1262A54a8135B",  # Polygon
        },
    },
}


# =============================================================================
# GAUGE CONTROLLERS (Mainnet only)
# =============================================================================

GAUGE_CONTROLLERS = {
    "curve": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
    "balancer": "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD",
    "frax": "0x3669C421b77340B2979d1A00a792CC2ee0FcE737",
    "fxn": "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37",
    "pendle": "0x44087E105137a5095c008AaB6a6530182821F2F0",
}


# =============================================================================
# GAUGE CONFIGURATION
# =============================================================================

VOTE_EVENT_HASHES = {
    "pendle": "0xc71e393f1527f71ce01b78ea87c9bd4fca84f1482359ce7ac9b73f358c61b1e1",
    "default": "0x45ca9a4c8d0119eb329e580d28fe689e484e1be230da8037ade9547d2d25cc91",
}

GAUGE_SLOTS = {
    "curve": {
        "point_weights": 12,
        "last_user_vote": 11,
        "vote_user_slope": 9,
    },
    "balancer": {
        "point_weights": 1000000008,
        "last_user_vote": 1000000007,
        "vote_user_slope": 1000000005,
    },
    "frax": {
        "point_weights": 1000000011,
        "last_user_vote": 1000000010,
        "vote_user_slope": 1000000008,
    },
    "fxn": {
        "point_weights": 1000000011,
        "last_user_vote": 1000000010,
        "vote_user_slope": 1000000008,
    },
    "pendle": {
        "point_weights": 161,
        "vote_user_slope": 162,
    },
}

CREATION_BLOCKS = {
    "curve": 10647875,
    "balancer": 14457014,
    "frax": 14052749,
    "fxn": 18156185,
    "pendle": 16032096,
}

VE_ADDRESSES = {
    "pendle": "0x4f30A9D41B80ecC5B94306AB4364951AE3170210",
}


# =============================================================================
# SIMPLE ACCESS FUNCTIONS
# =============================================================================


def get_platform(
    protocol: str, chain_id: int, version: str = "v1"
) -> Optional[str]:
    """Get VoteMarket platform address."""
    return (
        VOTEMARKET_PLATFORMS.get(protocol, {}).get(version, {}).get(chain_id)
    )


def get_all_platforms(protocol: str) -> List[Dict[str, any]]:
    """Get all platforms for a protocol across all chains and versions."""
    platforms = []
    protocol_data = VOTEMARKET_PLATFORMS.get(protocol, {})

    for version, chains in protocol_data.items():
        for chain_id, address in chains.items():
            platforms.append(
                {
                    "protocol": protocol,
                    "chain_id": chain_id,
                    "address": address,
                    "version": version,
                }
            )

    return platforms


def get_platforms_for_chain(chain_id: int) -> List[Dict[str, any]]:
    """Get all platforms on a specific chain."""
    platforms = []

    for protocol, versions in VOTEMARKET_PLATFORMS.items():
        for version, chains in versions.items():
            if chain_id in chains:
                platforms.append(
                    {
                        "protocol": protocol,
                        "chain_id": chain_id,
                        "address": chains[chain_id],
                        "version": version,
                    }
                )

    return platforms


def get_gauge_controller(protocol: str) -> Optional[str]:
    """Get gauge controller address for a protocol."""
    return GAUGE_CONTROLLERS.get(protocol)


def get_vote_event_hash(protocol: str) -> str:
    """Get vote event hash for a protocol."""
    return VOTE_EVENT_HASHES.get(protocol, VOTE_EVENT_HASHES["default"])


def get_gauge_slots(protocol: str) -> Optional[Dict[str, int]]:
    """Get gauge storage slots for a protocol."""
    return GAUGE_SLOTS.get(protocol)


def get_creation_block(protocol: str) -> Optional[int]:
    """Get creation block for a protocol."""
    return CREATION_BLOCKS.get(protocol)


def get_ve_address(protocol: str) -> Optional[str]:
    """Get VE token address for a protocol."""
    return VE_ADDRESSES.get(protocol)


# =============================================================================
# SUPPORTED PROTOCOLS & CHAINS
# =============================================================================

SUPPORTED_PROTOCOLS = list(VOTEMARKET_PLATFORMS.keys())
SUPPORTED_CHAINS = {
    1: "ethereum",
    10: "optimism",
    56: "bsc",
    137: "polygon",
    8453: "base",
    42161: "arbitrum",
}
