"""All constants for the project"""

import os

from dotenv import load_dotenv

load_dotenv()


class GaugeControllerConstants:
    """Global class constants Gauge Controller related ops"""

    VOTE_EVENT_HASH = {
        "pendle": "0xc71e393f1527f71ce01b78ea87c9bd4fca84f1482359ce7ac9b73f358c61b1e1",
        "default": "0x45ca9a4c8d0119eb329e580d28fe689e484e1be230da8037ade9547d2d25cc91"
    }

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

    GAUGE_CONTROLLER = {
        "curve": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
        "balancer": "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD",
        "frax": "0x3669C421b77340B2979d1A00a792CC2ee0FcE737",
        "fxn": "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37",
        "pendle": "0x44087E105137a5095c008AaB6a6530182821F2F0",
        "yb": "0x1Be14811A3a06F6aF4fA64310a636e1Df04c1c21",
    }

    CREATION_BLOCKS = {
        "curve": 10647875,
        "balancer": 14457014,
        "frax": 14052749,
        "fxn": 18156185,
        "pendle": 16032096,
        "yb": 23370933
    }

    VE_ADDRESSES = {
        "pendle": "0x4f30A9D41B80ecC5B94306AB4364951AE3170210"
    }


class GaugeVotesConstants:
    """Global class constants Gauge Votes related ops"""

    GAUGE_CONTROLLER = {
        "curve": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
        "balancer": "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD",
        "frax": "0x3669C421b77340B2979d1A00a792CC2ee0FcE737",
        "fxn": "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37",
        "pendle": "0x44087E105137a5095c008AaB6a6530182821F2F0",
        "yb": "0x1Be14811A3a06F6aF4fA64310a636e1Df04c1c21",
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

    CURVE = {
        1: None,
        42161: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
        10: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
        8453: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
        137: "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5",
    }

    CURVE_V2 = {
        42161: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",
        10: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",
        8453: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",
        137: "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9",
    }

    BALANCER = {
        1: None,
        42161: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",
        10: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",
        8453: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",
        137: "0xDD2FaD5606cD8ec0c3b93Eb4F9849572b598F4c7",
    }

    FXN = {
        1: None,
        42161: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
        10: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
        8453: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
        137: "0x155a7Cf21F8853c135BdeBa27FEA19674C65F2b4",
    }

    PENDLE = {
        1: None,
        42161: "0x105694FC5204787eD571842671d1262A54a8135B",
        10: "0x105694FC5204787eD571842671d1262A54a8135B",
        8453: "0x105694FC5204787eD571842671d1262A54a8135B",
        137: "0x105694FC5204787eD571842671d1262A54a8135B",
    }

    YB = {
        1: None,
        42161: "0x105694FC5204787eD571842671d1262A54a8135B",
        10: "0x105694FC5204787eD571842671d1262A54a8135B",
        8453: "0x105694FC5204787eD571842671d1262A54a8135B",
        137: "0x105694FC5204787eD571842671d1262A54a8135B",
    }

    @staticmethod
    def get_matching_contracts(base_name: str) -> list:
        """Get all contract names that match the base name pattern"""
        matches = []
        for attr_name in dir(ContractRegistry):
            if (
                not attr_name.startswith("__")
                and not callable(getattr(ContractRegistry, attr_name))
                and isinstance(getattr(ContractRegistry, attr_name), dict)
                and base_name.upper() in attr_name
            ):
                matches.append(attr_name)
        return matches

    @staticmethod
    def get_chains(contract_name: str) -> list:
        """Get list of chains where contract is deployed"""
        # Get all matching contracts
        matching_contracts = ContractRegistry.get_matching_contracts(
            contract_name
        )
        if not matching_contracts:
            raise ValueError(f"No contracts matching {contract_name} found")

        # Combine chains from all matching contracts
        all_chains = set()
        for contract in matching_contracts:
            addresses = getattr(ContractRegistry, contract)
            all_chains.update(
                chain for chain, addr in addresses.items() if addr is not None
            )
        return list(all_chains)

    @staticmethod
    def get_address(contract_name: str, chain_id: int) -> dict:
        """
        Get contract address(es) for specified chain
        Returns a dict of {contract_name: address} for all matching contracts
        """
        matching_contracts = ContractRegistry.get_matching_contracts(
            contract_name
        )
        if not matching_contracts:
            raise ValueError(f"No contracts matching {contract_name} found")

        results = {}
        for contract in matching_contracts:
            addresses = getattr(ContractRegistry, contract)
            if chain_id in addresses and addresses[chain_id] is not None:
                results[contract] = addresses[chain_id]

        if not results:
            raise ValueError(
                f"No matching contracts deployed on chain {chain_id}"
            )
        return results

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
        matching_contracts = (
            ContractRegistry.get_matching_contracts(pattern)
            if pattern
            else [
                attr_name
                for attr_name in dir(ContractRegistry)
                if not attr_name.startswith("__")
                and not callable(getattr(ContractRegistry, attr_name))
                and isinstance(getattr(ContractRegistry, attr_name), dict)
            ]
        )

        for contract_name in matching_contracts:
            contract_map = getattr(ContractRegistry, contract_name)
            if chain_id in contract_map and contract_map[chain_id] is not None:
                contracts[contract_name] = contract_map[chain_id]

        return contracts
