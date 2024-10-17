"""
Web3 Service module for interacting with Ethereum-based blockchains.

This module provides a Web3Service class that manages connections to different
blockchain networks, caches data, and offers various utility functions for
interacting with smart contracts and retrieving blockchain data.
"""

from w3multicall.multicall import W3Multicall
from web3 import Web3
from shared.utils import load_json
from typing import Dict, Any, List, Tuple, Optional


class Web3Service:
    """
    A service class for managing Web3 connections and interactions.

    This class provides methods for interacting with multiple blockchain networks,
    caching data, and performing common Web3 operations.
    """

    def __init__(
        self,
        default_chain_id: int = 1,
        default_rpc_url: str = "https://eth.meowrpc.com",
    ):
        """
        Initialize the Web3Service.

        Args:
            default_chain_id (int): The default chain ID to use. Defaults to 1 (Ethereum mainnet).
            default_rpc_url (str): The default RPC URL to use. Defaults to "https://eth.meowrpc.com".
        """
        self.w3: Dict[int, Web3] = {}
        self.initialize(default_chain_id, default_rpc_url)
        # Initialize the global service
        global web3_service
        web3_service = self

    def initialize(self, default_chain_id: int, default_rpc_url: str):
        """
        Initialize the service with default chain and caches.

        Args:
            default_chain_id (int): The default chain ID to use.
            default_rpc_url (str): The default RPC URL to use.
        """
        self.default_chain_id = default_chain_id
        self.add_chain(default_chain_id, default_rpc_url)
        self._latest_block_cache: Dict[Tuple[Optional[int], str], Dict[str, Any]] = {}
        self._token_info_cache: Dict[str, Dict[str, Any]] = {}
        self._contract_data_cache: Dict[
            Tuple[str, Tuple[Tuple[str, str], ...]], Dict[str, Any]
        ] = {}
        self._balance_cache: Dict[Tuple[str, Optional[int]], int] = {}
        self._erc20_balance_cache: Dict[Tuple[str, str], int] = {}
        self._block_cache: Dict[int, Dict[str, Any]] = {}
        self._contract_cache: Dict[Tuple[str, str], Any] = {}
        self._gwei_cache: Dict[int, float] = {}

    def add_chain(self, chain_id: int, rpc_url: str):
        """
        Add a new blockchain network to the service.

        Args:
            chain_id (int): The chain ID of the network to add.
            rpc_url (str): The RPC URL for the network.
        """
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3[chain_id] = w3

    def get_w3(self, chain_id: Optional[int] = None) -> Web3:
        """
        Get the Web3 instance for a specific chain ID.

        Args:
            chain_id (Optional[int]): The chain ID to get the Web3 instance for.
                If None, uses the default chain ID.

        Returns:
            Web3: The Web3 instance for the specified chain.

        Raises:
            ValueError: If the specified chain ID is not initialized.
        """
        if chain_id is None:
            chain_id = self.default_chain_id
        if chain_id not in self.w3:
            raise ValueError(f"Chain ID {chain_id} not initialized")
        return self.w3[chain_id]

    def get_latest_block(self, chain_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get the latest block information for a specific chain.

        Args:
            chain_id (Optional[int]): The chain ID to get the latest block for.
                If None, uses the default chain ID.

        Returns:
            Dict[str, Any]: The latest block information.
        """
        key = (chain_id, "latest")
        if key not in self._latest_block_cache:
            self._latest_block_cache[key] = self.get_w3(chain_id).eth.get_block(
                "latest"
            )
        return self._latest_block_cache[key]

    def get_token_info(
        self, token_addresses: List[str], chain_id: Optional[int] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get token information for a list of token addresses.

        Args:
            token_addresses (List[str]): List of token addresses to get information for.
            chain_id (Optional[int]): The chain ID to use. If None, uses the default chain ID.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary of token information, keyed by token address.
        """
        uncached_addresses = [
            addr for addr in token_addresses if addr not in self._token_info_cache
        ]
        if uncached_addresses:
            multicall = W3Multicall(self.get_w3(chain_id))
            for address in uncached_addresses:
                multicall.add(W3Multicall.Call(address, "name()(string)", []))
                multicall.add(W3Multicall.Call(address, "symbol()(string)", []))
                multicall.add(W3Multicall.Call(address, "decimals()(uint8)", []))

            call_results = multicall.call()

            for i, address in enumerate(uncached_addresses):
                self._token_info_cache[address] = {
                    "name": call_results[i * 3],
                    "symbol": call_results[i * 3 + 1],
                    "decimals": call_results[i * 3 + 2],
                }

        return {addr: self._token_info_cache[addr] for addr in token_addresses}

    def get_contract_data(
        self,
        contract_address: str,
        function_calls: List[Tuple[str, List[Any], str]],
        chain_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get contract data for multiple function calls.

        Args:
            contract_address (str): The address of the contract.
            function_calls (List[Tuple[str, List[Any], str]]): A list of tuples containing function names, arguments, and return types.
            chain_id (Optional[int]): The chain ID to use. If None, uses the default chain ID.

        Returns:
            Dict[str, Any]: A dictionary of function call results, keyed by function name.
        """
        key = (
            contract_address.lower(),
            tuple(
                (name, tuple(args), return_type)
                for name, args, return_type in function_calls
            ),
        )

        print(function_calls)

        if key not in self._contract_data_cache:
            multicall = W3Multicall(self.get_w3(chain_id))
            for func_name, args, return_type in function_calls:
                # Construct the function signature
                arg_types = ",".join(["address" for _ in args])
                signature = f"{func_name}({arg_types}){return_type}"
                multicall.add(W3Multicall.Call(contract_address, signature, args))

            call_results = multicall.call()

            self._contract_data_cache[key] = {}
            for i, (func_name, _, _) in enumerate(function_calls):
                try:
                    self._contract_data_cache[key][func_name] = call_results[i]
                except Exception as e:
                    print(f"Warning: Call to {func_name} failed. Error: {str(e)}")
                    self._contract_data_cache[key][func_name] = None

        return self._contract_data_cache[key]

    def get_erc20_balance(
        self, address: str, contract_address: str, chain_id: Optional[int] = None
    ) -> int:
        """
        Get the ERC20 token balance for a specific address.

        Args:
            address (str): The address to check the balance for.
            contract_address (str): The address of the ERC20 token contract.
            chain_id (Optional[int]): The chain ID to use. If None, uses the default chain ID.

        Returns:
            int: The token balance.
        """
        key = (address, contract_address)
        if key not in self._erc20_balance_cache:
            contract = self.get_contract(contract_address, "erc20", chain_id)
            self._erc20_balance_cache[key] = contract.functions.balanceOf(
                address
            ).call()
        return self._erc20_balance_cache[key]

    def get_block(
        self, block_identifier: int, chain_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get block information for a specific block number.

        Args:
            block_identifier (int): The block number to get information for.
            chain_id (Optional[int]): The chain ID to use. If None, uses the default chain ID.

        Returns:
            Dict[str, Any]: The block information.
        """
        if block_identifier not in self._block_cache:
            self._block_cache[block_identifier] = self.get_w3(chain_id).eth.get_block(
                block_identifier
            )
        return self._block_cache[block_identifier]

    # TODO : Store in disk
    def get_contract(self, address: str, abi_name: str, chain_id: Optional[int] = None):
        """
        Get a contract instance for a given address and ABI name.

        Args:
            address (str): The contract address.
            abi_name (str): The name of the ABI file (without .json extension).
            chain_id (Optional[int]): The chain ID to use. If None, uses the default chain ID.

        Returns:
            Contract: The contract instance.
        """
        key = (address, abi_name)
        if key not in self._contract_cache:
            abi = load_json(f"abi/{abi_name}.json")
            self._contract_cache[key] = self.get_w3(chain_id).eth.contract(
                address=Web3.to_checksum_address(address.lower()), abi=abi
            )
        return self._contract_cache[key]

    def get_gwei_price(
        self, block_number: int, chain_id: Optional[int] = None
    ) -> float:
        """
        Get the gas price in Gwei for a specific block.

        Args:
            block_number (int): The block number to get the gas price for.
            chain_id (Optional[int]): The chain ID to use. If None, uses the default chain ID.

        Returns:
            float: The gas price in Gwei.
        """
        key = block_number
        if key not in self._gwei_cache:
            block = self.get_block(block_number, chain_id)
            self._gwei_cache[key] = block["baseFeePerGas"]
        return self._gwei_cache[key] / 1e9

    def deploy_and_call_contract(
        self,
        abi: List[Dict[str, Any]],
        bytecode: str,
        constructor_args: List[Any],
        chain_id: Optional[int] = None,
    ) -> Any:
        """
        Deploy and call a contract in a single transaction.

        Args:
            abi (List[Dict[str, Any]]): The contract ABI.
            bytecode (str): The contract bytecode.
            constructor_args (List[Any]): The constructor arguments.
            chain_id (Optional[int]): The chain ID to use. If None, uses the default chain ID.

        Returns:
            Any: The result of the contract call.
        """
        w3 = self.get_w3(chain_id)
        contract = w3.eth.contract(abi=abi, bytecode=bytecode)
        construct_txn = contract.constructor(*constructor_args).build_transaction(
            {
                "from": "0x0000000000000000000000000000000000000000",  # This address doesn't matter for a call
                "nonce": 0,  # This nonce doesn't matter for a call
            }
        )
        result = w3.eth.call(construct_txn)
        return result


# Global instance
web3_service = None


def get_web3_service() -> Web3Service:
    """
    Get the global Web3Service instance.

    Returns:
        Web3Service: The global Web3Service instance.

    Raises:
        RuntimeError: If the Web3Service is not initialized.
    """
    if web3_service is None:
        raise RuntimeError(
            "Web3Service not initialized. Create a Web3Service instance first."
        )
    return web3_service
