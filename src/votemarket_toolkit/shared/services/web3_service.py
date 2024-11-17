"""
Web3 Service module for interacting with Ethereum-based blockchains.

This module provides a Web3Service class that manages connections to different
blockchain networks, caches data, and offers various utility functions for
interacting with smart contracts and retrieving blockchain data.
"""

from typing import Any, Dict, List

from web3 import Web3

from votemarket_toolkit.shared.constants import GlobalConstants
from votemarket_toolkit.shared.services.resource_manager import (
    resource_manager,
)


class Web3Service:
    """
    A service class for managing Web3 connections and interactions.

    This class provides methods for interacting with multiple blockchain networks,
    caching data, and performing common Web3 operations.
    """

    def __init__(
        self,
        chain_id: int,
        rpc_url: str,
    ):
        """
        Initialize the Web3Service.

        Args:
            chain_id (int): The chain ID to use.
            rpc_url (str): The RPC URL to use.
        """
        self.chain_id = chain_id
        self.w3 = self._initialize_web3(rpc_url)
        self._initialize_caches()

    def _initialize_web3(self, rpc_url: str) -> Web3:
        """Initialize Web3 instance with middleware if needed"""
        w3 = Web3(Web3.HTTPProvider(rpc_url))

        # Add POA middleware for non-mainnet chains
        if self.chain_id != 1:
            from web3.middleware import geth_poa_middleware

            w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        return w3

    def _initialize_caches(self):
        """Initialize all cache dictionaries"""
        self._latest_block_cache = {}
        self._token_info_cache = {}
        self._contract_data_cache = {}
        self._balance_cache = {}
        self._erc20_balance_cache = {}
        self._block_cache = {}
        self._contract_cache = {}
        self._gwei_cache = {}

    @classmethod
    def get_instance(cls, chain_id: int) -> "Web3Service":
        """Get or create a Web3Service instance for a specific chain"""
        if not hasattr(cls, "_instances"):
            cls._instances = {}

        if chain_id not in cls._instances:
            rpc_url = GlobalConstants.get_rpc_url(chain_id)
            cls._instances[chain_id] = cls(chain_id, rpc_url)

        return cls._instances[chain_id]

    def get_latest_block(self) -> Dict[str, Any]:
        """Get the latest block information"""
        key = "latest"
        if key not in self._latest_block_cache:
            self._latest_block_cache[key] = self.w3.eth.get_block("latest")
        return self._latest_block_cache[key]

    def get_block(self, block_identifier: int) -> Dict[str, Any]:
        """Get block information for a specific block number"""
        if block_identifier not in self._block_cache:
            self._block_cache[block_identifier] = self.w3.eth.get_block(
                block_identifier
            )
        return self._block_cache[block_identifier]

    def get_contract(self, address: str, abi_name: str) -> Any:
        """Get a contract instance for a given address and ABI name"""
        key = (address, abi_name)
        if key not in self._contract_cache:
            abi = resource_manager.load_abi(abi_name)
            self._contract_cache[key] = self.w3.eth.contract(
                address=Web3.to_checksum_address(address.lower()), abi=abi
            )
        return self._contract_cache[key]

    def get_gwei_price(self, block_number: int) -> float:
        """Get the gas price in Gwei for a specific block"""
        if block_number not in self._gwei_cache:
            block = self.get_block(block_number)
            self._gwei_cache[block_number] = block["baseFeePerGas"]
        return self._gwei_cache[block_number] / 1e9

    def deploy_and_call_contract(
        self,
        abi: List[Dict[str, Any]],
        bytecode: str,
        constructor_args: List[Any],
    ) -> Any:
        """Deploy and call a contract in a single transaction"""
        bytecode_data = resource_manager.load_bytecode(bytecode)
        contract = self.w3.eth.contract(
            abi=abi, bytecode=bytecode_data["bytecode"]
        )
        construct_txn = contract.constructor(
            *constructor_args
        ).build_transaction(
            {
                "from": "0x0000000000000000000000000000000000000000",
                "nonce": 0,
                "gas": 10000000,
            }
        )
        return self.w3.eth.call(construct_txn)
