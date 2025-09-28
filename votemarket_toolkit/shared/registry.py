"""
Registry for VoteMarket addresses and configuration.
Fetches data from the offchain-registry: https://github.com/stake-dao/offchain-registry
"""

from typing import Dict, List, Optional

import httpx


class Registry:
    """Registry that fetches data from the offchain-registry."""

    REGISTRY_URL = "https://raw.githubusercontent.com/stake-dao/offchain-registry/refs/heads/main/data/address-book/address-book.json"

    # Chain ID mapping
    CHAIN_NAMES = {
        1: "ethereum",
        10: "optimism",
        137: "polygon",
        8453: "base",
        42161: "arbitrum",
    }

    def __init__(self):
        self._data = None
        self._platforms = {}
        self._controllers = {}
        self._load_data()

    def _load_data(self):
        # Fetch from GitHub
        try:
            response = httpx.get(self.REGISTRY_URL, timeout=10)
            response.raise_for_status()
            self._data = response.json()
            self._parse_data()

        except Exception as e:
            print(f"Warning: Could not fetch registry: {str(e)[:100]}")

    def _parse_data(self):
        """Parse platforms and controllers from the registry data."""
        if not self._data:
            return

        # Parse platforms
        self._parse_platforms()

        # Add known historical platforms
        self._add_historical_platforms()

        # Parse gauge controllers
        self._parse_controllers()

    def _parse_platforms(self):
        """Parse VoteMarket platforms from registry."""
        self._platforms = {}

        for protocol_name in ["curve", "balancer", "fxn", "pendle", "frax"]:
            if protocol_name not in self._data:
                continue

            protocol_data = self._data[protocol_name]

            # Check each chain
            for chain_id, chain_name in self.CHAIN_NAMES.items():
                if (
                    chain_name not in protocol_data or chain_id == 1
                ):  # Skip Ethereum mainnet (no V2)
                    continue

                chain_data = protocol_data[chain_name]

                # Look for votemarket platforms
                if "votemarket" in chain_data:
                    vm_data = chain_data["votemarket"]

                    if isinstance(vm_data, dict):
                        # Current V2 platform
                        if "PLATFORM" in vm_data:
                            self._add_platform(
                                protocol_name,
                                chain_id,
                                vm_data["PLATFORM"],
                                "v2",
                            )
                        # V1 platform (might be labeled as PLATFORM_V1)
                        if "PLATFORM_V1" in vm_data:
                            self._add_platform(
                                protocol_name,
                                chain_id,
                                vm_data["PLATFORM_V1"],
                                "v1",
                            )

    def _add_platform(
        self, protocol: str, chain_id: int, address: str, version: str
    ):
        """Add a platform to the registry."""
        if protocol not in self._platforms:
            self._platforms[protocol] = {}
        if version not in self._platforms[protocol]:
            self._platforms[protocol][version] = {}
        self._platforms[protocol][version][chain_id] = address

    def _add_historical_platforms(self):
        """Add known historical platforms that might not be in the registry."""
        # First Curve V2 platform on Arbitrum (before the current one)
        # This was the first V2 deployment on L2s
        first_v2_address = "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5"

        # Add as v2_old for Curve on all L2 chains
        for chain_id in [
            42161,
            10,
            8453,
            137,
        ]:  # Arbitrum, Optimism, Base, Polygon
            self._add_platform("curve", chain_id, first_v2_address, "v2_old")

    def _parse_controllers(self):
        """Parse gauge controllers from registry."""
        self._controllers = {}

        if not self._data:
            return

        # Map of protocol to controller location in registry
        controller_paths = {
            "curve": ["curve", "ethereum", "protocol", "GAUGE_CONTROLLER"],
            "balancer": [
                "balancer",
                "ethereum",
                "protocol",
                "GAUGE_CONTROLLER",
            ],
            "frax": ["frax", "ethereum", "protocol", "GAUGE_CONTROLLER"],
            "fxn": ["fxn", "ethereum", "protocol", "GAUGE_CONTROLLER"],
            "pendle": ["pendle", "ethereum", "protocol", "GAUGE_CONTROLLER"],
        }

        for protocol, path in controller_paths.items():
            try:
                data = self._data
                for key in path:
                    data = data[key]
                self._controllers[protocol] = data
            except (KeyError, TypeError):
                pass


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_registry = None


def _get_registry():
    """Get or create the registry instance."""
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry


# =============================================================================
# PUBLIC API FUNCTIONS
# =============================================================================


def get_platform(
    protocol: str, chain_id: int, version: str = "v1"
) -> Optional[str]:
    """Get a specific VoteMarket platform address."""
    registry = _get_registry()

    protocol_lower = protocol.lower()
    if protocol_lower in registry._platforms:
        if version in registry._platforms[protocol_lower]:
            return registry._platforms[protocol_lower][version].get(chain_id)
    return None


def get_all_platforms(protocol: str) -> List[Dict]:
    """Get all platforms for a protocol across all chains."""
    registry = _get_registry()

    result = []
    protocol_lower = protocol.lower()

    if protocol_lower in registry._platforms:
        for version, chains in registry._platforms[protocol_lower].items():
            for chain_id, address in chains.items():
                result.append(
                    {
                        "protocol": protocol_lower,
                        "chain_id": chain_id,
                        "address": address,
                        "version": version,
                    }
                )

    return result


def get_chain_for_platform(platform_address: str) -> Optional[int]:
    """Get chain ID for a given platform address."""
    registry = _get_registry()

    platform_lower = platform_address.lower()
    for protocol, versions in registry._platforms.items():
        for version, chains in versions.items():
            for chain_id, address in chains.items():
                if address.lower() == platform_lower:
                    return chain_id
    return None


def get_platforms_for_chain(chain_id: int) -> List[Dict]:
    """Get all platforms on a specific chain."""
    registry = _get_registry()

    result = []
    for protocol, versions in registry._platforms.items():
        for version, chains in versions.items():
            if chain_id in chains:
                result.append(
                    {
                        "protocol": protocol,
                        "chain_id": chain_id,
                        "address": chains[chain_id],
                        "version": version,
                    }
                )

    return result


def get_gauge_controller(protocol: str) -> Optional[str]:
    """Get gauge controller address for a protocol."""
    registry = _get_registry()
    return registry._controllers.get(protocol.lower())


def get_gauge_slots(protocol: str) -> Optional[Dict[str, int]]:
    """Get gauge storage slots for a protocol."""
    # These slots are constants - could be moved to registry in future
    slots = {
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
    return slots.get(protocol.lower())


def refresh_registry():
    """Force refresh the registry from GitHub."""
    registry = _get_registry()
    registry.refresh()


# =============================================================================
# STATIC CONFIGURATION (protocol-specific constants)
# =============================================================================


def get_vote_event_hash(protocol: str) -> str:
    """Get vote event hash for a protocol."""
    # Pendle uses a different event signature
    if protocol.lower() == "pendle":
        # VoteForGaugeWeight(address indexed user, address indexed pool, uint256 weight, VoteResult vote)
        return "0xc71e393f1527f71ce01b78ea87c9bd4fca84f1482359ce7ac9b73f358c61b1e1"
    else:
        # VoteForGauge(uint256 time, address user, address gauge_addr, uint256 weight)
        return "0x45ca9a4c8d0119eb329e580d28fe689e484e1be230da8037ade9547d2d25cc91"


def get_creation_block(protocol: str) -> Optional[int]:
    """Get creation block for a protocol gauge controller."""
    # These are the deployment blocks of gauge controllers on mainnet
    # Could be fetched from a more comprehensive registry in future
    blocks = {
        "curve": 10647875,  # Curve gauge controller deployment
        "balancer": 14457014,  # Balancer gauge controller deployment
        "frax": 14052749,  # Frax gauge controller deployment
        "fxn": 18156185,  # FXN gauge controller deployment
        "pendle": 16032096,  # Pendle gauge controller deployment
    }
    return blocks.get(protocol.lower())


def get_ve_address(protocol: str) -> Optional[str]:
    """Get VE token address for a protocol."""
    registry = _get_registry()

    # Try to get from registry
    if registry._data and protocol.lower() in registry._data:
        try:
            protocol_data = registry._data[protocol.lower()]
            if (
                "ethereum" in protocol_data
                and "protocol" in protocol_data["ethereum"]
            ):
                if "VEPENDLE" in protocol_data["ethereum"]["protocol"]:
                    return protocol_data["ethereum"]["protocol"]["VEPENDLE"]
                if (
                    "VE" + protocol.upper()
                    in protocol_data["ethereum"]["protocol"]
                ):
                    return protocol_data["ethereum"]["protocol"][
                        "VE" + protocol.upper()
                    ]
        except (KeyError, TypeError):
            pass

    return None


def get_supported_protocols() -> List[str]:
    """Get list of supported protocols."""
    registry = _get_registry()
    return list(registry._platforms.keys())


def get_supported_chains() -> Dict[int, str]:
    """Get supported chains."""
    return Registry.CHAIN_NAMES.copy()
