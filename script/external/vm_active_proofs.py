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
from votes.main import VMVotes
from votes.query_campaigns import query_active_campaigns

load_dotenv()

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

TEMP_DIR = "temp"

"""
This script generates active proofs, based on inputs
provided by vm_all_platforms.py. It's part of automated process for
generating and storing proofs to be used in the API.
"""

vm_proofs = VoteMarketProofs(1)
vm_votes = VMVotes(1)

async def process_protocol(protocol_data: Dict[str, Any], CURRENT_EPOCH: int) -> Dict[str, Any]:
    """
    Process a protocol to generate active proofs.

    Args:
        protocol_data (Dict[str, Any]): The data for a single protocol.
        CURRENT_EPOCH (int): The current voting epoch.

    Returns:
        Dict[str, Any]: A dictionary containing the processed protocol data with active proofs.
    """
    protocol = protocol_data["protocol"]
    platforms = protocol_data["platforms"]

    protocol_data = {"name": protocol, "gauge_controller_proof": "", "platforms": {}}

    # Get gauge controller proof once for the protocol
    logging.info(f"Generating gauge controller proof for {protocol}")
    gauge_proofs = vm_proofs.get_gauge_proof(
        protocol=protocol,
        gauge_address="0x0000000000000000000000000000000000000000",  # Dummy address
        CURRENT_EPOCH=CURRENT_EPOCH,
        block_number=platforms[0]["latest_setted_block"],  # Use the first platform's block number
    )

    protocol_data["gauge_controller_proof"] = "0x" + gauge_proofs["gauge_controller_proof"].hex()

    web3_service = Web3Service(1, GlobalConstants.CHAIN_ID_TO_RPC[1])

    for platform_data in platforms:
        chain_id = platform_data['chain_id']
        platform = platform_data['platform']
        block_number = platform_data['latest_setted_block']

        logging.info(f"Processing platform: {platform} on chain {chain_id}")

        if chain_id not in web3_service.w3:
            logging.info(f"Adding new chain to Web3 service: {chain_id}")
            web3_service.add_chain(chain_id, GlobalConstants.CHAIN_ID_TO_RPC[chain_id])

        logging.info(f"Querying active campaigns for platform: {platform}")
        active_campaigns = query_active_campaigns(web3_service, chain_id, platform)

        # TODO: remove this dummy data once the real function is implemented
        active_campaigns = [
            {
                "id": 0,
                "chain_id": chain_id,
                "gauge": "0xf1bb643f953836725c6e48bdd6f1816f871d3e07",
                "blacklist": [
                    "0xdead000000000000000000000000000000000000",
                    "0x0100000000000000000000000000000000000000",
                ],
            },
            {
                "id": 1,
                "chain_id": chain_id,
                "gauge": "0x059e0db6bf882f5fe680dc5409c7adeb99753736",
                "blacklist": [
                    "0xdead000000000000000000000000000000000000",
                    "0x0100000000000000000000000000000000000000",
                ],
            },
        ]

        platform_data = {
            "chain_id": chain_id,
            "platform_address": platform,
            "block_number": block_number,
            "gauges": {},
        }

        logging.info(f"Processing {len(active_campaigns)} campaigns")
        for campaign in active_campaigns:
            gauge_address = campaign["gauge"]
            logging.info(f"Processing gauge: {gauge_address}")

            gauge_data = {
                "point_data_proof": "",
                "users": {},
                "blacklisted_users": {},
            }

            # Get point data proof for the specific gauge
            logging.info(f"Generating point data proof for gauge: {gauge_address}")
            gauge_proofs = vm_proofs.get_gauge_proof(
                protocol=protocol,
                gauge_address=gauge_address,
                CURRENT_EPOCH=CURRENT_EPOCH,
                block_number=block_number,
            )
            gauge_data["point_data_proof"] = "0x" + gauge_proofs["point_data_proof"].hex()

            # Get eligible users
            logging.info(f"Fetching eligible users for gauge: {gauge_address}")
            eligible_users = await vm_votes.get_eligible_users(
                protocol, gauge_address, CURRENT_EPOCH, block_number
            )
            logging.info(f"Found {len(eligible_users)} eligible users for gauge: {gauge_address}")

            for user in eligible_users:
                user_address = user["user"]
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

            # Process blacklisted users
            logging.info(f"Processing blacklisted users for gauge: {gauge_address}")
            for blacklisted_user in campaign["blacklist"]:
                logging.info(f"Generating proof for blacklisted user: {blacklisted_user}")
                user_proofs = vm_proofs.get_user_proof(
                    protocol=protocol,
                    gauge_address=gauge_address,
                    user=blacklisted_user,
                    block_number=block_number,
                )
                gauge_data["blacklisted_users"][blacklisted_user] = {
                    "storage_proof": "0x" + user_proofs["storage_proof"].hex(),
                }

            platform_data["gauges"][gauge_address] = gauge_data

        protocol_data["platforms"][platform] = platform_data

    logging.info(f"Finished processing protocol: {protocol}")
    return protocol_data

async def main(all_platforms_file: str, CURRENT_EPOCH: int):
    """
    Main function to process all protocols and generate active proofs.

    Args:
        all_platforms_file (str): Path to the JSON file containing all platforms data.
        CURRENT_EPOCH (int): The current voting epoch.
    """
    logging.info(f"Starting active proofs generation for epoch: {CURRENT_EPOCH}")
    logging.info(f"Reading platforms data from: {all_platforms_file}")

    with open(all_platforms_file, 'r') as f:
        all_platforms_data = json.load(f)

    for protocol_data in all_platforms_data["protocols"]:
        logging.info(f"Processing protocol: {protocol_data['protocol']}")
        processed_data = await process_protocol(protocol_data, CURRENT_EPOCH)

        json_data = {
            "epoch": CURRENT_EPOCH,
            **processed_data
        }

        # Store in a json file
        os.makedirs(TEMP_DIR, exist_ok=True)
        output_file = f"{TEMP_DIR}/{processed_data['name']}_active_proofs.json"
        with open(output_file, "w") as f:
            json.dump(json_data, f, indent=2)

        logging.info(f"Saved data for {processed_data['name']} to {output_file}")

    logging.info("Finished generating active proofs for all protocols")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate active proofs for protocols")
    parser.add_argument(
        "all_platforms_file",
        type=str,
        help="Path to the JSON file containing all platforms data",
    )
    parser.add_argument("CURRENT_EPOCH", type=int, help="Current epoch timestamp")

    args = parser.parse_args()

    logging.info("Starting active proofs generation script")
    asyncio.run(main(args.all_platforms_file, args.CURRENT_EPOCH))
    logging.info("Active proofs generation script completed")