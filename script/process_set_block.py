import os
from dotenv import load_dotenv
from eth_utils import keccak
from eth_abi import encode as eth_abi_encode
from proofs.VMProofs import VoteMarketProofs
from shared.utils import get_closest_block_timestamp

load_dotenv()

# Initialize Web3 and VoteMarketProofs
vm_proofs = VoteMarketProofs(
    "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
)


def get_current_period():
    current_block = vm_proofs.web3_service.get_w3().eth.get_block("latest")
    current_timestamp = current_block["timestamp"]
    return current_timestamp - (current_timestamp % (7 * 24 * 3600))


def encode_insert_block_number(epoch, block_info):
    block_header = {
        "hash": bytes.fromhex(block_info["BlockHash"][2:]),
        "stateRootHash": bytes.fromhex("0" * 64),
        "number": block_info["BlockNumber"],
        "timestamp": block_info["BlockTimestamp"],
    }

    # ABI encode the function call
    function_signature = keccak(
        text="insertBlockNumber(uint256,(bytes32,bytes32,uint256,uint256))"
    )[:4]
    encoded_params = eth_abi_encode(
        ["uint256", "(bytes32,bytes32,uint256,uint256)"],
        [epoch, list(block_header.values())],
    )

    return function_signature + encoded_params


if __name__ == "__main__":
    current_period = get_current_period()



    block = get_closest_block_timestamp("ethereum", current_period)

    # Block infos
    block_info = vm_proofs.get_block_info(block)

    print(block_info)


    encoded_calldata = encode_insert_block_number(current_period, block_info)

    print(f"Current Period: {current_period}")
    print(f"Block Number: {block_info['BlockNumber']}")
    print(f"Block Hash: {block_info['BlockHash']}")
    print(f"Encoded Calldata: {'0x' + encoded_calldata.hex()}")