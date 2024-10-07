import logging
import os
from dotenv import load_dotenv
from eth_utils import keccak
from eth_abi import encode as eth_abi_encode
from proofs.main import VoteMarketProofs
from shared.utils import get_closest_block_timestamp
import json
import argparse

load_dotenv()

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

TEMP_DIR = "temp"

# Initialize Web3 and VoteMarketProofs
vm_proofs = VoteMarketProofs(1)


def get_current_epoch():
    logging.info("Fetching current epoch")
    current_block = vm_proofs.web3_service.get_w3().eth.get_block("latest")
    current_timestamp = current_block["timestamp"]
    epoch = current_timestamp - (current_timestamp % (7 * 24 * 3600))
    logging.info(f"Current epoch: {epoch}")
    return epoch


if __name__ == "__main__":
    logging.info("Starting vm_block_data script")

    current_epoch = get_current_epoch()

    parser = argparse.ArgumentParser()
    parser.add_argument("--block", type=int, help="Specific block number to use")
    args = parser.parse_args()

    if args.block:
        block = args.block
        logging.info(f"Using provided block number: {block}")
    else:
        logging.info(f"Getting closest block for timestamp: {current_epoch}")
        block = get_closest_block_timestamp("ethereum", current_epoch)
        logging.info(f"Closest block number: {block}")

    logging.info("Fetching block info")
    block_info = vm_proofs.get_block_info(block)
    logging.info(f"Block info retrieved for block {block}")

    json_data = {
        "epoch": current_epoch,
        "block_header": block_info,
    }

    logging.info("Preparing to save data")
    os.makedirs(TEMP_DIR, exist_ok=True)
    output_file = f"{TEMP_DIR}/current_epoch_block_data.json"

    with open(output_file, "w") as f:
        json.dump(json_data, f, indent=2)

    logging.info(f"Saved data to {output_file}")
    logging.info("vm_block_data script completed")
