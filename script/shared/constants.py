""" All constants for the project """

import os

from dotenv import load_dotenv

load_dotenv()


class GaugeControllerConstants:
    """Global class constants Gauge Controller related ops"""

    VOTE_EVENT_HASH = (
        "0x45ca9a4c8d0119eb329e580d28fe689e484e1be230da8037ade9547d2d25cc91"
    )

    GAUGES_SLOTS = {
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
            "point_weights": 10000000011,
            "last_user_vote": 1000000010,
            "vote_user_slope": 1000000008,
        },
        "fxn": {
            "point_weights": 10000000011,
            "last_user_vote": 1000000010,
            "vote_user_slope": 1000000008,
        },
    }

    GAUGE_CONTROLLER = {
        "curve": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
        "balancer": "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD",
        "frax": "0x3669C421b77340B2979d1A00a792CC2ee0FcE737",
        "fxn": "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37",
    }

    CREATION_BLOCKS = {
        "curve": 10647875,
        "balancer": 14457014,
        "frax": 14052749,
        "fxn": 18156185,
    }


class GaugeVotesConstants:
    """Global class constants Gauge Votes related ops"""

    GAUGE_CONTROLLER = {
        "curve": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
        "balancer": "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD",
        "frax": "0x3669C421b77340B2979d1A00a792CC2ee0FcE737",
        "fxn": "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37",
    }


class GlobalConstants:
    """Global class constants for the project"""

    WEEK = 604800

    CHAIN_ID_TO_RPC = {
        1: os.getenv("ETHEREUM_MAINNET_RPC_URL") or None,
        10: os.getenv("OPTIMISM_MAINNET_RPC_URL") or None,
        42161: os.getenv("ARBITRUM_MAINNET_RPC_URL") or None,
        8453: os.getenv("BASE_MAINNET_RPC_URL") or None,
        137: os.getenv("POLYGON_MAINNET_RPC_URL") or None,
        56: os.getenv("BSC_MAINNET_RPC_URL") or None,
    }

    @staticmethod
    def get_rpc_url(chain_id: int) -> str:
        """Get RPC URL for specified chain"""
        chain_id = int(chain_id)
        if chain_id not in GlobalConstants.CHAIN_ID_TO_RPC:
            raise ValueError(f"Chain ID {chain_id} not supported")

        rpc_url = GlobalConstants.CHAIN_ID_TO_RPC[chain_id]
        if not rpc_url:
            raise ValueError(f"RPC URL not set for chain {chain_id}")

        return rpc_url


class ContractRegistry:
    """
    Central registry of contracts across chains.
    Format: CONTRACT_NAME = {chain_id: address}
    """

    # VOTEMARKET
    ORACLE = {
        1: None,  # Not deployed on mainnet
        42161: "0x36F5B50D70df3D3E1c7E1BAf06c32119408Ef7D8",  # Arbitrum
        10: "0x36F5B50D70df3D3E1c7E1BAf06c32119408Ef7D8",  # Optimism
        8453: "0x36F5B50D70df3D3E1c7E1BAf06c32119408Ef7D8",  # Base
        137: "0x36F5B50D70df3D3E1c7E1BAf06c32119408Ef7D8",  # Polygon
    }

    CURVE = {
        1: None,
        42161: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
        10: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
        8453: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
        137: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
    }

    @staticmethod
    def get_address(contract_name: str, chain_id: int) -> str:
        """Get contract address for specified chain"""
        addresses = getattr(ContractRegistry, contract_name, None)
        if not addresses:
            raise ValueError(f"Contract {contract_name} not found")
        address = addresses.get(chain_id)
        if not address:
            raise ValueError(
                f"Contract {contract_name} not deployed on chain {chain_id}"
            )
        return address

    @staticmethod
    def get_chains(contract_name: str) -> list:
        """Get list of chains where contract is deployed"""
        addresses = getattr(ContractRegistry, contract_name, None)

        if not addresses:
            raise ValueError(f"Contract {contract_name} not found")
        return [chain for chain, addr in addresses.items() if addr is not None]

    @staticmethod
    def get_contracts_for_chain(chain_id: int, pattern: str = None) -> dict:
        """
        Get all contracts deployed on a specific chain, optionally filtered by a pattern
        Args:
            chain_id: Chain ID to query
            pattern: Optional filter (e.g., "VOTEMARKET" or "CURVE")
        Returns: dict of {contract_name: address}
        """
        contracts = {}
        for attr_name in dir(ContractRegistry):
            # Skip special methods and non-contract attributes
            if attr_name.startswith("__") or attr_name in [
                "get_address",
                "get_chains",
                "get_contracts_for_chain",
            ]:
                continue

            # Apply pattern filter if provided
            if pattern and pattern.upper() not in attr_name:
                continue

            # Get the contract mapping
            contract_map = getattr(ContractRegistry, attr_name)
            if (
                isinstance(contract_map, dict)
                and chain_id in contract_map
                and contract_map[chain_id] is not None
            ):
                contracts[attr_name] = contract_map[chain_id]

        return contracts
