import logging
import os
from dotenv import load_dotenv
from eth_utils import keccak
from eth_abi import encode as eth_abi_encode
from proofs.main import VoteMarketProofs
from shared.constants import GlobalConstants
from shared.utils import get_closest_block_timestamp
import json

load_dotenv()

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

TEMP_DIR = "temp"

# Initialize Web3 and VoteMarketProofs
vm_proofs = VoteMarketProofs(
    1, GlobalConstants.CHAIN_ID_TO_RPC[1]
)


def get_current_period():
    current_block = vm_proofs.web3_service.get_w3().eth.get_block("latest")
    current_timestamp = current_block["timestamp"]
    return current_timestamp - (current_timestamp % (7 * 24 * 3600))


if __name__ == "__main__":
    current_period = get_current_period()

    block = get_closest_block_timestamp("ethereum", current_period)

    # Block infos
    block_info = vm_proofs.get_block_info(block)

    json_data = {
        "epoch": current_period,
        "block_header": block_info,
    }

    # Store in a json file
    os.makedirs(TEMP_DIR, exist_ok=True)
    with open(TEMP_DIR + "/current_period_block_data.json", "w") as f:
        json.dump(json_data, f)

    logging.info(f"Saved data to {TEMP_DIR}/current_period_block_data.json")
