from w3multicall.multicall import W3Multicall
from web3 import Web3
from shared.utils import load_json
from typing import Dict, Any, List, Tuple


class Web3Service:
    def __init__(self, default_chain_id=1, default_rpc_url="https://eth.meowrpc.com	"):
        self.w3 = {}
        self.initialize(default_chain_id, default_rpc_url)

    def initialize(self, default_chain_id, default_rpc_url):
        self.default_chain_id = default_chain_id
        self.add_chain(default_chain_id, default_rpc_url)
        self._latest_block_cache = {}
        self._token_info_cache = {}
        self._contract_data_cache = {}
        self._balance_cache = {}
        self._erc20_balance_cache = {}
        self._block_cache = {}
        self._contract_cache = {}
        self._gwei_cache = {}

    def add_chain(self, chain_id, rpc_url):
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3[chain_id] = w3

    def get_w3(self, chain_id=1): # Default to mainnet
        if chain_id is None:
            chain_id = self.default_chain_id
        if chain_id not in self.w3:
            raise ValueError(f"Chain ID {chain_id} not initialized")
        return self.w3[chain_id]

    def get_latest_block(self, chain_id=None) -> Dict[str, Any]:
        key = (chain_id, "latest")
        if key not in self._latest_block_cache:
            self._latest_block_cache[key] = self.get_w3(chain_id).eth.get_block("latest")
        return self._latest_block_cache[key]

    def get_token_info(self, token_addresses: List[str]) -> Dict[str, Dict[str, Any]]:
        uncached_addresses = [
            addr for addr in token_addresses if addr not in self._token_info_cache
        ]
        if uncached_addresses:
            multicall = W3Multicall(self.get_w3())
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
        self, contract_address: str, function_calls: List[Tuple[str, str]]
    ) -> Dict[str, Any]:
        key = (contract_address, tuple(function_calls))
        if key not in self._contract_data_cache:
            multicall = W3Multicall(self.get_w3())
            for func_name, return_type in function_calls:
                multicall.add(
                    W3Multicall.Call(contract_address, f"{func_name}{return_type}", [])
                )

            call_results = multicall.call()

            self._contract_data_cache[key] = {
                func_name: call_results[i]
                for i, (func_name, _) in enumerate(function_calls)
            }

        return self._contract_data_cache[key]

    def get_erc20_balance(self, address: str, contract_address: str) -> int:
        key = (address, contract_address)
        if key not in self._erc20_balance_cache:
            contract = self.get_contract(contract_address, "erc20")
            self._erc20_balance_cache[key] = contract.functions.balanceOf(
                address
            ).call()
        return self._erc20_balance_cache[key]

    def get_block(self, block_identifier: int) -> Dict[str, Any]:
        if block_identifier not in self._block_cache:
            self._block_cache[block_identifier] = self.get_w3().eth.get_block(
                block_identifier
            )
        return self._block_cache[block_identifier]

    def get_contract(self, address: str, abi_name: str):
        key = (address, abi_name)
        if key not in self._contract_cache:
            abi = load_json("abi/" + abi_name + ".json")
            self._contract_cache[key] = self.get_w3().eth.contract(
                address=Web3.to_checksum_address(address.lower()), abi=abi
            )
        return self._contract_cache[key]

    def get_gwei_price(self, block_number: int) -> float:
        key = block_number
        if key not in self._gwei_cache:
            block = self.get_block(block_number)
            self._gwei_cache[key] = block["baseFeePerGas"]
        return self._gwei_cache[key] / 1e9


# Global instance
web3_service = None


def initialize_web3_service(default_chain_id, default_rpc_url):
    global web3_service
    web3_service = Web3Service(default_chain_id, default_rpc_url)


def get_web3_service():
    if web3_service is None:
        raise RuntimeError(
            "Web3Service not initialized. Call initialize_web3_service first."
        )
    return web3_service
