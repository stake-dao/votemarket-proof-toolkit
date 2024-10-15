import json
import os
import argparse
import logging
from typing import List, Dict, Any
from eth_utils import to_checksum_address
from dotenv import load_dotenv
from shared.constants import GlobalConstants
from shared.web3_service import Web3Service
from votes.query_campaigns import get_all_platforms
from proofs.main import VoteMarketProofs
from shared.utils import get_closest_block_timestamp
from shared.types import ProtocolData, AllProtocolsData

load_dotenv()

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

TEMP_DIR = "temp"

"""
This script generates a JSON file containing information about all platforms
for specified protocols. It's designed to be used in conjunction with
vm_active_proofs.py as part of the automated process of generating proofs.
"""


def get_block_data(block_number: int) -> Dict:
    print(f"Getting block data for block number: {block_number}")
    vm_proofs = VoteMarketProofs(1)
    block_info = vm_proofs.get_block_info(block_number)
    return {
        "block_number": block_info["block_number"],
        "block_hash": block_info["block_hash"],
        "block_timestamp": block_info["block_timestamp"],
        "rlp_block_header": block_info["rlp_block_header"],
    }


def process_protocol(protocol: str, epoch: int) -> ProtocolData:
    """
    Process a single protocol to gather platform information.

    Args:
        protocol (str): The name of the protocol to process.
        epoch (int): The epoch to use for fetching data.

    Returns:
        ProtocolData: A dictionary containing the protocol name and a list of platform data.
    """
    logging.info(f"Processing protocol: {protocol}")
    platforms = get_all_platforms(protocol)
    logging.info(f"Found {len(platforms)} platforms for {protocol}")

    web3_service = Web3Service(1, GlobalConstants.CHAIN_ID_TO_RPC[1])

    protocol_data: ProtocolData = {"protocol": protocol, "platforms": {}}

    for platform in platforms:
        chain_id = platform["chain_id"]
        platform_address = platform["address"]
        logging.info(f"Processing platform: {platform_address} on chain {chain_id}")

        if chain_id not in web3_service.w3:
            logging.info(f"Adding new chain to Web3 service: {chain_id}")
            web3_service.add_chain(chain_id, GlobalConstants.CHAIN_ID_TO_RPC[chain_id])

        # Fetch the oracle address from platform
        logging.info(f"Fetching oracle address for platform: {platform_address}")
        platform_contract = web3_service.get_contract(platform_address, "vm_platform", chain_id)
        lens = platform_contract.functions.ORACLE().call()
        lens_address = to_checksum_address(lens.lower())

        # Fetch real oracle address from lens
        lens_contract = web3_service.get_contract(lens_address, "oracle_lens", chain_id)
        oracle_address = lens_contract.functions.oracle().call()
        oracle_address = to_checksum_address(oracle_address.lower())

        if oracle_address == "0x0000000000000000000000000000000000000000":
            logging.warning(f"Skipping platform {platform_address} as it doesn't have an oracle")
            continue

        logging.info(f"Fetching latest setted block from oracle for epoch: {epoch}")
        oracle = web3_service.get_contract(oracle_address, "oracle", chain_id)
        latest_setted_block = oracle.functions.epochBlockNumber(epoch).call()[2]

        platform["latest_setted_block"] = latest_setted_block
        logging.info(
            f"Set latest_setted_block for platform {platform_address} on epoch {epoch}: {platform['latest_setted_block']}"
        )

        # Get block data for the latest setted block
        block_data = get_block_data(latest_setted_block)
        timestamp = block_data["block_timestamp"]
        block_period_timestamp = (
            timestamp // GlobalConstants.WEEK
        ) * GlobalConstants.WEEK

        current_period_timestamp = (
            epoch // GlobalConstants.WEEK
        ) * GlobalConstants.WEEK

        if block_period_timestamp < current_period_timestamp:
            logging.error(
                f"Latest setted block period ({block_period_timestamp}) is less than current period ({current_period_timestamp}) for platform {platform_address}. Skipping this platform."
            )
            continue

        platform["block_data"] = block_data
        protocol_data["platforms"][platform_address] = platform

    return protocol_data


def main(protocols: List[str], epoch: int) -> AllProtocolsData:
    all_protocols_data: AllProtocolsData = {"protocols": {}}

    for protocol in protocols:
        protocol_data = process_protocol(protocol, epoch)
        all_protocols_data["protocols"][protocol] = protocol_data

    os.makedirs(TEMP_DIR, exist_ok=True)
    output_file = f"{TEMP_DIR}/all_platforms.json"
    with open(output_file, "w") as f:
        json.dump(all_protocols_data, f, indent=2)

    print(f"Saved data for all protocols to {output_file}")
    return all_protocols_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a list of all platforms for given protocols"
    )
    parser.add_argument(
        "protocols",
        type=str,
        nargs="+",
        help="List of protocol names (e.g., 'curve', 'balancer')",
    )
    parser.add_argument(
        "--epoch",
        type=int,
        required=True,
        help="epoch to use for fetching latest block on the ORACLE",
    )

    args = parser.parse_args()
    main(args.protocols, args.epoch)
