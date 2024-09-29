import asyncio
import json
import logging
import os
import argparse
from typing import List, Dict, Any

from dotenv import load_dotenv
from proofs.VMProofs import VoteMarketProofs
from votes.VMVotes import VMVotes
from votes.query_campaigns import get_all_platforms, query_active_campaigns

load_dotenv()

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

TEMP_DIR = "temp"

vm_proofs = VoteMarketProofs(
    "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
)
vm_votes = VMVotes(
    "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
)

async def process_protocol(
    protocol: str, block_number: int, current_period: int
) -> Dict[str, Any]:
    # Get all platforms for the protocol # TODO : Registry
    # chain_platforms = get_all_platforms(protocol)
    chain_platforms = [
        (1, "0x0000000000000000000000000000000000000000"),
    ]
    protocol_data = {
        "name": protocol,
        "gauge_controller_proof": "",
        "platforms": {}
    }

    # Get gauge controller proof once for the protocol
    gauge_controller_proof, _ = vm_proofs.get_gauge_proof(
        protocol=protocol,
        gauge_address="0x0000000000000000000000000000000000000000",  # Dummy address
        current_period=current_period,
        block_number=block_number,
    )
    protocol_data["gauge_controller_proof"] = "0x" + gauge_controller_proof.hex()

    for chain_id, platform in chain_platforms:
        # active_campaigns = query_active_campaigns(chain_id, platform)
        active_gauges = ["0xfb18127c1471131468a1aad4785c19678e521d86", "0x059e0db6bf882f5fe680dc5409c7adeb99753736"]
        platform_data = {
            "chain_id": chain_id,
            "platform_address": platform,
            "gauges": {}
        }

        for gauge_address in active_gauges:
            gauge_data = {"point_data_proof": "", "users": {}}

            # Get point data proof for the specific gauge
            _, point_data_proof = vm_proofs.get_gauge_proof(
                protocol=protocol,
                gauge_address=gauge_address,
                current_period=current_period,
                block_number=block_number,
            )
            gauge_data["point_data_proof"] = "0x" + point_data_proof.hex()

            # Get eligible users
            eligible_users = await vm_votes.get_eligible_users(
                protocol, gauge_address, current_period, block_number
            )

            for user in eligible_users:
                user_address = user["user"]
                # Get user proof
                _, user_storage_proof = vm_proofs.get_user_proof(
                    protocol=protocol,
                    gauge_address=gauge_address,
                    user=user_address,
                    block_number=block_number,
                )
                gauge_data["users"][user_address] = {
                    "storage_proof": "0x" + user_storage_proof.hex(),
                    "last_vote": user["last_vote"],
                    "slope": user["slope"],
                    "power": user["power"],
                    "end": user["end"],
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
            "protocol": protocol_data
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
    parser.add_argument("protocols", type=str, nargs='+', help="List of protocol names (e.g., 'curve', 'balancer')")
    parser.add_argument("block_number", type=int, help="Block number to use for proofs")
    parser.add_argument("current_period", type=int, help="Current period timestamp")

    args = parser.parse_args()

    asyncio.run(main(args.protocols, args.block_number, args.current_period))
