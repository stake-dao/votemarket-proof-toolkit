import asyncio
import json
import logging
import os
import argparse
from typing import List, Dict, Any

from dotenv import load_dotenv
from proofs.main import VoteMarketProofs
from shared.constants import GlobalConstants
from shared.web3_service import Web3Service
from votes.main import VoteMarketVotes
from votes.query_campaigns import query_active_campaigns
from shared.types import AllProtocolsData

load_dotenv()

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

TEMP_DIR = "temp"

"""
This script generates active proofs, based on inputs
provided by vm_all_platforms.py. It's part of automated process for
generating and storing proofs to be used in the API.
"""

vm_proofs = VoteMarketProofs(1)
vm_votes = VoteMarketVotes(1)


async def process_protocol(
    protocol_data: Dict[str, Any], current_epoch: int
) -> Dict[str, Any]:
    """
    Process a protocol to generate active proofs.

    Args:
        protocol_data (Dict[str, Any]): The data for a single protocol.
        current_epoch (int): The current voting epoch.

    Returns:
        Dict[str, Any]: A dictionary containing the processed protocol data with active proofs.
    """

    protocol = protocol_data["protocol"].lower()
    platforms = {k.lower(): v for k, v in protocol_data["platforms"].items()}

    # Initialize the output dictionary with block_data at the beginning
    output_data = {
        "block_data": platforms[list(platforms.keys())[0]]["block_data"],
        "gauge_controller_proof": "",
        "platforms": {},
    }

    # Get gauge controller proof once for the protocol
    logging.info(f"Generating gauge controller proof for {protocol}")
    gauge_proofs = vm_proofs.get_gauge_proof(
        protocol=protocol,
        gauge_address="0x0000000000000000000000000000000000000000",  # Dummy address
        current_epoch=current_epoch,
        block_number=platforms[list(platforms.keys())[0]][
            "latest_setted_block"
        ],  # Use the first platform's block number
    )

    output_data["gauge_controller_proof"] = (
        "0x" + gauge_proofs["gauge_controller_proof"].hex()
    )

    web3_service = Web3Service(1, GlobalConstants.CHAIN_ID_TO_RPC[1])

    for platform_address, platform_data in platforms.items():
        chain_id = platform_data["chain_id"]
        block_number = platform_data["latest_setted_block"]

        logging.info(f"Processing platform: {platform_address} on chain {chain_id}")

        if chain_id not in web3_service.w3:
            logging.info(f"Adding new chain to Web3 service: {chain_id}")
            web3_service.add_chain(chain_id, GlobalConstants.CHAIN_ID_TO_RPC[chain_id])

        logging.info(f"Querying active campaigns for platform: {platform_address}")
        active_campaigns = query_active_campaigns(
            web3_service, chain_id, platform_address
        )

        platform_data = {
            "chain_id": chain_id,
            "platform_address": platform_address.lower(),
            "gauges": {},
        }

        logging.info(f"Processing {len(active_campaigns)} campaigns")
        for campaign in active_campaigns:
            gauge_address = campaign["gauge"].lower()
            logging.info(f"Processing gauge: {gauge_address}")

            gauge_data = {
                "point_data_proof": "",
                "users": {},
                "listed_users": {},
            }

            # Get point data proof for the specific gauge
            logging.info(f"Generating point data proof for gauge: {gauge_address}")
            gauge_proofs = vm_proofs.get_gauge_proof(
                protocol=protocol,
                gauge_address=gauge_address,
                current_epoch=current_epoch,
                block_number=block_number,
            )
            gauge_data["point_data_proof"] = (
                "0x" + gauge_proofs["point_data_proof"].hex()
            )

            # Get eligible users
            logging.info(f"Fetching eligible users for gauge: {gauge_address}")
            eligible_users = await vm_votes.get_eligible_users(
                protocol, gauge_address, current_epoch, block_number
            )
            logging.info(
                f"Found {len(eligible_users)} eligible users for gauge: {gauge_address}"
            )

            for user in eligible_users:
                user_address = user["user"].lower()
                logging.info(f"Generating proof for user: {user_address}")
                # Get user proof
                user_proofs = vm_proofs.get_user_proof(
                    protocol=protocol,
                    gauge_address=gauge_address,
                    user=user_address,
                    block_number=block_number,
                )
                gauge_data["users"][user_address] = {
                    "storage_proof": "0x" + user_proofs["storage_proof"].hex(),
                    "last_vote": user["last_vote"],
                    "slope": user["slope"],
                    "power": user["power"],
                    "end": user["end"],
                }

            # Process listed (white + blacklist) users
            logging.info(f"Processing whitelisted or blacklisted users for gauge: {gauge_address}")
            for listed_user in campaign["listed_users"]:
                logging.info(
                    f"Generating proof for listed user: {listed_user}"
                )
                user_proofs = vm_proofs.get_user_proof(
                    protocol=protocol,
                    gauge_address=gauge_address,
                    user=listed_user,
                    block_number=block_number,
                )
                gauge_data["listed_users"][listed_user.lower()] = {
                    "storage_proof": "0x" + user_proofs["storage_proof"].hex(),
                }

            platform_data["gauges"][gauge_address] = gauge_data

        output_data["platforms"][platform_address.lower()] = platform_data

    logging.info(f"Finished processing protocol: {protocol}")
    return output_data


def write_protocol_data(protocol: str, current_epoch: int, processed_data: Dict[str, Any]):
    """
    Write processed protocol data to files in the specified structure.

    Args:
        protocol (str): The protocol name.
        current_epoch (int): The current voting epoch.
        processed_data (Dict[str, Any]): The processed data for the protocol.
    """
    protocol_dir = os.path.join(TEMP_DIR, protocol.lower())
    os.makedirs(protocol_dir, exist_ok=True)

    # Write header.json
    header_data = {
        "epoch": current_epoch,
        "block_data": processed_data["block_data"],
        "gauge_controller_proof": processed_data["gauge_controller_proof"]
    }
    with open(os.path.join(protocol_dir, "header.json"), "w") as f:
        json.dump(header_data, f, indent=2)

    # Write main.json (contains all data for the protocol)
    main_data = {
        "epoch": current_epoch,
        "block_data": processed_data["block_data"],
        "gauge_controller_proof": processed_data["gauge_controller_proof"],
        "platforms": processed_data["platforms"]
    }
    with open(os.path.join(protocol_dir, "index.json"), "w") as f:
        json.dump(main_data, f, indent=2)

    # Process platforms
    for platform_address, platform_data in processed_data["platforms"].items():
        chain_id = platform_data["chain_id"]
        platform_folder_name = f"{platform_address.lower()}"
        chain_dir = os.path.join(protocol_dir, f"{chain_id}")
        os.makedirs(chain_dir, exist_ok=True)
        platform_dir = os.path.join(chain_dir, platform_folder_name)
        os.makedirs(platform_dir, exist_ok=True)

        # Write gauge files
        for gauge_address, gauge_data in platform_data["gauges"].items():
            gauge_file = os.path.join(platform_dir, f"{gauge_address.lower()}.json")
            with open(gauge_file, "w") as f:
                json.dump(gauge_data, f, indent=2)

    logging.info(f"Saved data for {protocol} in {protocol_dir}")


async def main(all_protocols_data: AllProtocolsData, current_epoch: int):
    """
    Main function to process all protocols and generate active proofs.

    Args:
        all_protocols_data (AllProtocolsData): Data containing all protocols and platforms.
        current_epoch (int): The current voting epoch.
    """
    logging.info(f"Starting active proofs generation for epoch: {current_epoch}")

    for protocol, protocol_data in all_protocols_data["protocols"].items():
        if len(protocol_data["platforms"]) == 0:
            logging.info(f"Skipping protocol: {protocol} as no platforms found")
            continue
        logging.info(f"Processing protocol: {protocol}")
        processed_data = await process_protocol(protocol_data, current_epoch)
        write_protocol_data(protocol.lower(), current_epoch, processed_data)

    logging.info("Finished generating active proofs for all protocols")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate active proofs for protocols")
    parser.add_argument(
        "all_platforms_file",
        type=str,
        help="Path to the JSON file containing all platforms data",
    )
    parser.add_argument("current_epoch", type=int, help="Current epoch timestamp")

    args = parser.parse_args()

    logging.info("Starting active proofs generation script")

    with open(args.all_platforms_file, "r") as f:
        all_protocols_data = json.load(f)

    asyncio.run(main(all_protocols_data, args.current_epoch))
    logging.info("Active proofs generation script completed")
