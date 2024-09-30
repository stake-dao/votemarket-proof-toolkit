from typing import List, Any
from solcx import compile_source
from shared.web3_service import get_web3_service


class ContractReader:
    @staticmethod
    def read_contract_data(
        contract_source: str, constructor_args: List[Any], chain_id: int
    ) -> Any:
        web3_service = get_web3_service()

        compiled_sol = compile_source(contract_source)
        contract_interface = compiled_sol["<stdin>:BatchCampaignData"]

        # Deploy and call the contract
        result = web3_service.deploy_and_call_contract(
            contract_interface["abi"],
            contract_interface["bin"],
            constructor_args,
            chain_id,
        )

        return result

    @staticmethod
    def decode_result(abi: List[str], result: bytes) -> Any:
        from eth_abi import decode

        return decode(abi, result)[0]
