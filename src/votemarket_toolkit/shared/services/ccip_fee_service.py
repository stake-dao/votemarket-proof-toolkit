from typing import Any, Dict, List

from eth_utils import to_checksum_address

from votemarket_toolkit.contracts.reader import ContractReader
from votemarket_toolkit.shared.services.resource_manager import (
    resource_manager,
)
from votemarket_toolkit.utils.file_utils import load_json

CCIP_ADAPTER_ADDRESS = "0x4200740090f72e89302f001da5860000007d7ea7"


class CcipFeeService:
    def __init__(self, w3, ccip_router_address: str):
        self.w3 = w3
        self.ccip_router_address = ccip_router_address
        self.adapter = self.w3.eth.contract(
            address=to_checksum_address(CCIP_ADAPTER_ADDRESS),
            abi=load_json(
                "src/votemarket_toolkit/resources/abi/ccip_adapter.json"
            ),
        )

    def get_ccip_fee(
        self,
        dest_chain_id: int,
        execution_gas_limit: int,
        receiver: str,
        tokens: List[Dict[str, Any]],
        additional_data: bytes,
    ) -> int:
        """Calculate CCIP fee for a specific chain"""

        # Load bytecode using resource manager
        bytecode_data = resource_manager.load_bytecode("GetCCIPFee")

        # Get bridge chain ID from adapter
        bridge_chain_id = self.adapter.functions.getBridgeChainId(
            dest_chain_id
        ).call()

        # Format tokens for the contract call
        formatted_tokens = [
            {
                "tokenAddress": to_checksum_address(token["address"]),
                "amount": int(token["amount"]),
            }
            for token in tokens
        ]

        # Build constructor transaction
        tx = ContractReader.build_get_ccip_fee_constructor_tx(
            artifact={"bytecode": bytecode_data},
            router_address=to_checksum_address(self.ccip_router_address),
            dest_chain_selector=bridge_chain_id,
            dest_chain_id=dest_chain_id,
            receiver=to_checksum_address(receiver),
            execution_gas_limit=execution_gas_limit,
            tokens=formatted_tokens,
            payload=additional_data,
        )

        # Execute call
        result = self.w3.eth.call(tx)

        # Decode result
        fee = ContractReader.decode_result(["uint256"], result)[0]

        # Add 20% buffer to fee
        return int(fee * 1.2)
