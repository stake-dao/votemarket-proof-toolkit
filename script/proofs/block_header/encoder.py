""" Block header encoder """

from typing import Any, Dict
from web3 import Web3
from hexbytes import HexBytes
import rlp

from shared.types import BlockInfo

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
    """Encode a block header -> RLP encoded"""
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


def get_block_info(web_3: Web3, block_number: int) -> BlockInfo:
    """Get block info -> block number, block hash, block timestamp, rlp encoded block header"""
    block = web_3.eth.get_block(block_number)
    encoded_header = encode_block_header(block)

    return {
        "BlockNumber": block_number,
        "BlockHash": block["hash"].hex(),
        "BlockTimestamp": block["timestamp"],
        "RlpBlockHeader": "0x" + encoded_header.hex(),
    }
