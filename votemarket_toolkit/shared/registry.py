"""
Registry for VoteMarket addresses and configuration.
Fetches data from the offchain-registry: https://github.com/stake-dao/offchain-registry
"""

import copy
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class Registry:
    """Registry that fetches data from the offchain-registry."""

    REGISTRY_URL = "https://raw.githubusercontent.com/stake-dao/offchain-registry/refs/heads/main/data/address-book/address-book.json"

    # Chain ID mapping — includes all chains present in the address-book
    CHAIN_NAMES = {
        1: "ethereum",
        10: "optimism",
        137: "polygon",
        252: "fraxtal",
        8453: "base",
        42161: "arbitrum",
        42793: "etherlink",
        146: "sonic",
        167000: "taiko",
    }

    # Map registry protocol keys to internal short names
    PROTOCOL_MAPPING = {
        "curve": "curve",
        "balancer": "balancer",
        "fxn": "fxn",
        "pendle": "pendle",
        "frax": "frax",
        "yieldbasis": "yb",
    }

    # Controller contract name per protocol in the registry
    CONTROLLER_CONTRACT_NAMES = {
        "curve": "GAUGE_CONTROLLER",
        "balancer": "GAUGE_CONTROLLER",
        "frax": "GAUGE_CONTROLLER",
        "fxn": "GAUGE_CONTROLLER",
        "pendle": "VOTING_CONTROLLER",
        "yieldbasis": "GAUGE_CONTROLLER",
    }

    # Contract category for the controller lookup — defaults to "protocol" when absent
    CONTROLLER_CATEGORIES = {
        "pendle": "locker",  # VOTING_CONTROLLER lives under the locker category
    }

    # VE token contract name per protocol in the registry
    VE_CONTRACT_NAMES = {
        "curve": "VECRV",
        "balancer": "VEBAL",
        "frax": "VEFXS",
        "fxn": "VEFXN",
        "pendle": "VEPENDLE",
        "yieldbasis": "VE_YB",
    }

    # Emission token contract name per protocol in the registry
    EMISSION_TOKEN_CONTRACT_NAMES = {
        "curve": "CRV",
        "balancer": "BAL",
        "fxn": "FXN",
        "frax": "FXS",
        "pendle": "PENDLE",
    }

    # Fallback emission token addresses for protocols absent from registry (pendle)
    FALLBACK_EMISSION_TOKENS = {
        "curve": "0xD533a949740bb3306d119CC777fa900bA034cd52",
        "balancer": "0xba100000625a3754423978a60c9317c58a424e3D",
        "fxn": "0x365AccFCa291e7D3914637ABf1F7635dB165Bb09",
        "frax": "0x3432B6A60D23Ca0dFCa7761B7ab56459D9C964D0",
        "pendle": "0x808507121B80c02388fAd14726482e061B8da827",
    }

    # Fallback platform addresses (used when GitHub fetch fails or protocol absent from registry)
    FALLBACK_PLATFORMS = {
        "curve": {
            "v2": {
                42161: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",
                10: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",
                8453: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",
                137: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",
            },
            "v2_old": {
                42161: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
                10: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
                8453: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
                137: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
            },
        },
        "balancer": {
            "v2": {
                42161: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",
                10: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",
                8453: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",
                137: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",
            },
        },
        "fxn": {
            "v2": {
                42161: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
                10: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
                8453: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
                137: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
            },
        },
        "pendle": {
            "v2": {
                42161: "0x105694FC5204787eD571842671d1262A54a8135B",
                10: "0x105694FC5204787eD571842671d1262A54a8135B",
                8453: "0x105694FC5204787eD571842671d1262A54a8135B",
                137: "0x105694FC5204787eD571842671d1262A54a8135B",
            },
        },
        "frax": {
            "v2": {
                42161: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
                10: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
                8453: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
                137: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
            },
        },
    }

    # Fallback gauge controllers (used when GitHub fetch fails or protocol absent from registry)
    FALLBACK_CONTROLLERS = {
        "curve": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
        "balancer": "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD",
        "frax": "0x3669C421b77340B2979d1A00a792CC2ee0FcE737",
        "fxn": "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37",
        "pendle": "0x44087E105137a5095c008AaB6a6530182821F2F0",
        "yb": "0x1Be14811A3a06F6aF4fA64310a636e1Df04c1c21",
    }

    # Fallback VE token addresses for protocols absent from the registry (pendle, yb)
    FALLBACK_VE_ADDRESSES = {
        "pendle": "0x4f30A9D41B80ecC5B94306AB4364951AE3170210",
    }

    def __init__(self):
        self._data = None
        self._platforms = {}
        self._controllers = {}
        self._ve_addresses = {}
        self._emission_tokens = {}
        self._load_data()

    def _load_data(self) -> None:
        try:
            response = httpx.get(self.REGISTRY_URL, timeout=10)
            response.raise_for_status()
            self._data = response.json()
        except (httpx.HTTPError, httpx.RequestError, OSError) as e:
            logger.warning("Could not fetch registry from GitHub: %s", str(e)[:100])
            logger.warning("Using fallback static registry data")
            self._use_fallback_data()
            return

        try:
            self._parse_data()
        except Exception as e:
            logger.error(
                "Failed to parse registry data: %s — using fallback static data",
                str(e)[:200],
            )
            self._use_fallback_data()

    def _use_fallback_data(self) -> None:
        self._platforms = copy.deepcopy(self.FALLBACK_PLATFORMS)
        self._controllers = copy.deepcopy(self.FALLBACK_CONTROLLERS)
        self._ve_addresses = copy.deepcopy(self.FALLBACK_VE_ADDRESSES)
        self._emission_tokens = copy.deepcopy(self.FALLBACK_EMISSION_TOKENS)

    def _parse_data(self) -> None:
        if not self._data:
            return

        protocols = self._data.get("protocols", {})

        self._parse_platforms(protocols)
        self._add_historical_platforms()
        self._parse_controllers(protocols)
        self._parse_ve_addresses(protocols)
        self._parse_emission_tokens(protocols)

        # Fill in any protocols absent from the live registry with fallback data
        self._merge_fallbacks_for_missing_protocols()

    # -------------------------------------------------------------------------
    # Parsing helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _find_contract(
        contracts: List[Dict[str, Any]],
        name: str,
        category: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the first contract matching name (and optionally category)."""
        for c in contracts:
            if c.get("name") != name:
                continue
            if category is not None and c.get("category") != category:
                continue
            return c
        return None

    def _get_chain_contracts(self, protocol_data: Dict[str, Any], chain_name: str) -> List[Dict[str, Any]]:
        """Return the contracts array for a given chain inside a protocol entry."""
        return (
            protocol_data.get("chains", {})
            .get(chain_name, {})
            .get("contracts", [])
        )

    # -------------------------------------------------------------------------
    # Platform parsing
    # -------------------------------------------------------------------------

    def _parse_platforms(self, protocols: Dict[str, Any]) -> None:
        self._platforms = {}

        for registry_name, internal_name in self.PROTOCOL_MAPPING.items():
            if registry_name not in protocols:
                continue

            protocol_data = protocols[registry_name]

            for chain_id, chain_name in self.CHAIN_NAMES.items():
                contracts = self._get_chain_contracts(protocol_data, chain_name)
                if not contracts:
                    continue

                platform = self._find_contract(contracts, "PLATFORM", "votemarket")
                if platform and platform.get("address"):
                    version = "v1" if chain_id == 1 else "v2"
                    self._add_platform(internal_name, chain_id, platform["address"], version)

                platform_v1 = self._find_contract(contracts, "PLATFORM_V1", "votemarket")
                if platform_v1 and platform_v1.get("address"):
                    self._add_platform(internal_name, chain_id, platform_v1["address"], "v1")

    def _add_platform(self, protocol: str, chain_id: int, address: str, version: str) -> None:
        if protocol not in self._platforms:
            self._platforms[protocol] = {}
        if version not in self._platforms[protocol]:
            self._platforms[protocol][version] = {}
        self._platforms[protocol][version][chain_id] = address

    def _add_historical_platforms(self) -> None:
        """Add known historical platforms absent from the registry (first Curve V2 on L2s)."""
        first_v2_address = "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5"
        for chain_id in [42161, 10, 8453, 137]:
            self._add_platform("curve", chain_id, first_v2_address, "v2_old")

    # -------------------------------------------------------------------------
    # Controller parsing
    # -------------------------------------------------------------------------

    def _parse_controllers(self, protocols: Dict[str, Any]) -> None:
        self._controllers = {}

        for registry_name, internal_name in self.PROTOCOL_MAPPING.items():
            if registry_name not in protocols:
                continue

            controller_name = self.CONTROLLER_CONTRACT_NAMES.get(registry_name)
            if not controller_name:
                continue

            category = self.CONTROLLER_CATEGORIES.get(registry_name, "protocol")
            contracts = self._get_chain_contracts(protocols[registry_name], "ethereum")
            contract = self._find_contract(contracts, controller_name, category)
            if contract and contract.get("address"):
                self._controllers[internal_name] = contract["address"]
            else:
                logger.warning(
                    "Registry: %s not found for %s (category=%s) — will use fallback",
                    controller_name,
                    registry_name,
                    category,
                )

    # -------------------------------------------------------------------------
    # VE address parsing
    # -------------------------------------------------------------------------

    def _parse_ve_addresses(self, protocols: Dict[str, Any]) -> None:
        self._ve_addresses = {}

        for registry_name, internal_name in self.PROTOCOL_MAPPING.items():
            if registry_name not in protocols:
                continue

            ve_name = self.VE_CONTRACT_NAMES.get(registry_name)
            if not ve_name:
                continue

            contracts = self._get_chain_contracts(protocols[registry_name], "ethereum")
            contract = self._find_contract(contracts, ve_name, "protocol")
            if contract and contract.get("address"):
                self._ve_addresses[internal_name] = contract["address"]

    # -------------------------------------------------------------------------
    # Emission token parsing
    # -------------------------------------------------------------------------

    def _parse_emission_tokens(self, protocols: Dict[str, Any]) -> None:
        self._emission_tokens = {}

        for registry_name, internal_name in self.PROTOCOL_MAPPING.items():
            if registry_name not in protocols:
                continue

            token_name = self.EMISSION_TOKEN_CONTRACT_NAMES.get(registry_name)
            if not token_name:
                continue

            contracts = self._get_chain_contracts(protocols[registry_name], "ethereum")
            contract = self._find_contract(contracts, token_name, "protocol")
            if contract and contract.get("address"):
                self._emission_tokens[internal_name] = contract["address"]

    # -------------------------------------------------------------------------
    # Fallback merge for protocols absent from registry
    # -------------------------------------------------------------------------

    def _merge_fallbacks_for_missing_protocols(self) -> None:
        """For any protocol not found in the live registry, inject fallback data."""
        for protocol, versions in self.FALLBACK_PLATFORMS.items():
            if protocol not in self._platforms:
                self._platforms[protocol] = copy.deepcopy(versions)

        for protocol, address in self.FALLBACK_CONTROLLERS.items():
            if protocol not in self._controllers:
                self._controllers[protocol] = address

        for protocol, address in self.FALLBACK_VE_ADDRESSES.items():
            if protocol not in self._ve_addresses:
                self._ve_addresses[protocol] = address

        for protocol, address in self.FALLBACK_EMISSION_TOKENS.items():
            if protocol not in self._emission_tokens:
                self._emission_tokens[protocol] = address


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_registry = None


def _get_registry():
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
    protocol_lower = protocol.lower()
    if protocol_lower in registry._controllers:
        return registry._controllers[protocol_lower]
    return Registry.FALLBACK_CONTROLLERS.get(protocol_lower)


def get_gauge_slots(protocol: str) -> Optional[Dict[str, int]]:
    """Get gauge storage slots for a protocol."""
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
        "yb": {
            "point_weights": 1000000006,
            "last_user_vote": 1000000005,
            "vote_user_slope": 1000000003,
        },
    }
    return slots.get(protocol.lower())


def refresh_registry():
    """Force refresh the registry from GitHub."""
    global _registry
    _registry = None
    _get_registry()


# =============================================================================
# STATIC CONFIGURATION (protocol-specific constants)
# =============================================================================


def get_token_factory_address() -> str:
    """Get LaPoste TokenFactory address (same for all chains)."""
    return "0x96006425Da428E45c282008b00004a00002B345e"


def get_vote_event_hash(protocol: str) -> str:
    """Get vote event hash for a protocol."""
    if protocol.lower() == "pendle":
        return "0xc71e393f1527f71ce01b78ea87c9bd4fca84f1482359ce7ac9b73f358c61b1e1"
    else:
        return "0x45ca9a4c8d0119eb329e580d28fe689e484e1be230da8037ade9547d2d25cc91"


def get_creation_block(protocol: str) -> Optional[int]:
    """Get creation block for a protocol gauge controller."""
    blocks = {
        "curve": 10647875,
        "balancer": 14457014,
        "frax": 14052749,
        "fxn": 18156185,
        "pendle": 16032096,
        "yb": 23370933,
    }
    return blocks.get(protocol.lower())


def get_emission_token(protocol: str) -> Optional[str]:
    """Get emission token address for a protocol (e.g. CRV, BAL, FXN, FXS, PENDLE)."""
    registry = _get_registry()
    protocol_lower = protocol.lower()
    if protocol_lower in registry._emission_tokens:
        return registry._emission_tokens[protocol_lower]
    return Registry.FALLBACK_EMISSION_TOKENS.get(protocol_lower)


def get_ve_address(protocol: str) -> Optional[str]:
    """Get VE token address for a protocol."""
    registry = _get_registry()
    protocol_lower = protocol.lower()
    if protocol_lower in registry._ve_addresses:
        return registry._ve_addresses[protocol_lower]
    return Registry.FALLBACK_VE_ADDRESSES.get(protocol_lower)


def get_supported_protocols() -> List[str]:
    """Get list of supported protocols."""
    registry = _get_registry()
    return list(registry._platforms.keys())


def get_supported_chains() -> Dict[int, str]:
    """Get supported chains."""
    return Registry.CHAIN_NAMES.copy()


def get_chain_name(chain_id: int) -> str:
    """
    Get the display name for a chain ID.

    Args:
        chain_id: The chain ID (e.g., 1, 42161)

    Returns:
        Human-readable chain name in title case (e.g., "Ethereum", "Arbitrum")
    """
    name = Registry.CHAIN_NAMES.get(chain_id)
    if name:
        return name.title()
    return f"Chain {chain_id}"
