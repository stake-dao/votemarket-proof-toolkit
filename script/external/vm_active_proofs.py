import asyncio
import json
import logging
import os
import argparse
from typing import List, Dict, Any

from dotenv import load_dotenv
from proofs.main import VoteMarketProofs
from shared.constants import GlobalConstants
from shared.types import Platform
from shared.web3_service import Web3Service
from votes.main import VMVotes
from votes.query_campaigns import get_all_platforms, query_active_campaigns

load_dotenv()

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

TEMP_DIR = "temp"

vm_proofs = VoteMarketProofs(
    1, GlobalConstants.CHAIN_ID_TO_RPC[1]
)
vm_votes = VMVotes(
    1, GlobalConstants.CHAIN_ID_TO_RPC[1]
)


async def process_protocol(
    protocol: str, block_number: int, current_period: int
) -> Dict[str, Any]:
    # Get all platforms for the protocol
    chain_platforms: List[Platform] = get_all_platforms(protocol)

    print(chain_platforms)

    protocol_data = {"name": protocol, "gauge_controller_proof": "", "platforms": {}}

    # Get gauge controller proof once for the protocol
    gauge_proofs = vm_proofs.get_gauge_proof(
        protocol=protocol,
        gauge_address="0x0000000000000000000000000000000000000000",  # Dummy address
        current_period=current_period,
        block_number=block_number,
    )

    protocol_data["gauge_controller_proof"] = "0x" + gauge_proofs["gauge_controller_proof"].hex()

    web3_service = Web3Service(1, GlobalConstants.CHAIN_ID_TO_RPC[1])

    for platform_data in chain_platforms:
        chain_id = platform_data['chain_id']
        platform = platform_data['platform']
        if chain_id not in web3_service.w3:
            web3_service.add_chain(chain_id, GlobalConstants.CHAIN_ID_TO_RPC[chain_id])

        active_campaigns = query_active_campaigns(web3_service, chain_id, platform)

        # TODO : remove this
        active_campaigns = [
            {
                "id": 0,
                "chain_id": 42161,
                "gauge": "0xf1bb643f953836725c6e48bdd6f1816f871d3e07",
                "blacklist": [
                    "0xdead000000000000000000000000000000000000",
                    "0x0100000000000000000000000000000000000000",
                ],
            },
            {
                "id": 1,
                "chain_id": 42161,
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
            "gauges": {},
        }

        for campaign in active_campaigns:
            gauge_address = campaign["gauge"]
            gauge_data = {
                "point_data_proof": "",
                "users": {},
                "blacklisted_users": {},
            }

            # Get point data proof for the specific gauge
            gauge_proofs = vm_proofs.get_gauge_proof(
                protocol=protocol,
                gauge_address=gauge_address,
                current_period=current_period,
                block_number=block_number,
            )
            gauge_data["point_data_proof"] = "0x" + gauge_proofs["point_data_proof"].hex()

            # Get eligible users
            eligible_users = await vm_votes.get_eligible_users(
                protocol, gauge_address, current_period, block_number
            )

            for user in eligible_users:
                user_address = user["user"]
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
            for blacklisted_user in campaign["blacklist"]:
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

    return protocol_data


async def main(protocols: List[str], block_number: int, current_period: int):
    for protocol in protocols:
        protocol_data = await process_protocol(protocol, block_number, current_period)

        json_data = {
            "block_number": block_number,
            "period": current_period,
            **protocol_data
        }

        # Store in a json file
        os.makedirs(TEMP_DIR, exist_ok=True)
        with open(f"{TEMP_DIR}/{protocol}_active_proofs.json", "w") as f:
            json.dump(json_data, f, indent=2)

        logging.info(
            f"Saved data for {protocol} to {TEMP_DIR}/{protocol}_active_proofs.json"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate active proofs for protocols")
    parser.add_argument(
        "protocols",
        type=str,
        nargs="+",
        help="List of protocol names (e.g., 'curve', 'balancer')",
    )
    parser.add_argument("block_number", type=int, help="Block number to use for proofs")
    parser.add_argument("current_period", type=int, help="Current period timestamp")

    args = parser.parse_args()

    asyncio.run(main(args.protocols, args.block_number, args.current_period))
