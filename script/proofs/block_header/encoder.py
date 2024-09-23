from typing import Any, Dict
from web3 import Web3
from hexbytes import HexBytes
import rlp

BLOCK_HEADER = (
    "parentHash",
    "sha3Uncles",
    "miner",
    "stateRoot",
    "transactionsRoot",
    "receiptsRoot",
    "logsBloom",
    "difficulty",
    "number",
    "gasLimit",
    "gasUsed",
    "timestamp",
    "extraData",
    "mixHash",
    "nonce",
    "baseFeePerGas",
    "withdrawalsRoot",
    "blobGasUsed",
    "excessBlobGas",
    "parentBeaconBlockRoot",
)

def encode_block_header(block: Dict[str, Any]) -> bytes:
    block_header = [
        (
            HexBytes("0x")
            if isinstance(block.get(k), int) and block.get(k) == 0
            else HexBytes(block.get(k))
        )
        for k in BLOCK_HEADER
        if k in block
    ]
    return rlp.encode(block_header)


def get_block_info(w3: Web3, block_number: int) -> Dict[str, Any]:
    block = w3.eth.get_block(block_number)

    print(block)
    encoded_header = encode_block_header(block)


    return {
        "BlockNumber": block_number,
        "BlockHash": block["hash"].hex(),
        "BlockTimestamp": block["timestamp"],
        "RlpBlockHeader": encoded_header.hex(),
    }
