from typing import Any, List

from shared.web3_service import Web3Service
from solcx import compile_source


class ContractReader:
    @staticmethod
    def read_contract_data(
        contract_source: str,
        constructor_args: List[Any],
        web3_service: Web3Service,
    ) -> Any:
        compiled_sol = compile_source(contract_source)
        contract_interface = compiled_sol["<stdin>:BatchCampaignData"]

        # Deploy and call the contract
        result = web3_service.deploy_and_call_contract(
            contract_interface["abi"],
            contract_interface["bin"],
            constructor_args,
        )

        return result

    @staticmethod
    def decode_result(abi: List[str], result: bytes) -> Any:
        from eth_abi import decode

        return decode(abi, result)[0]
