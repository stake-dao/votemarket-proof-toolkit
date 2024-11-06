"""
Process a protocol to generate active proofs.

This script handles the generation of proofs for protocols, including:
- Gauge controller proof
- Point data proof for each gauge
- User proofs for eligible users and listed users

It processes all platforms and gauges associated with the protocols and returns
a dictionary containing the processed data with active proofs.
"""

import asyncio
import json
import os
import argparse
from typing import Dict, Any, List

from dotenv import load_dotenv
from proofs.main import VoteMarketProofs
from shared.constants import GlobalConstants
from shared.utils import get_rounded_epoch
from shared.web3_service import Web3Service
from data.main import VoteMarketData
from data.query_campaigns import query_active_campaigns
from shared.types import AllProtocolsData, ProtocolData
from rich.console import Console
from rich.panel import Panel

load_dotenv()

TEMP_DIR = "temp"

vm_proofs = VoteMarketProofs(1)
vm_votes = VoteMarketData(1)
console = Console()


async def process_protocol(
    protocol: str,
    protocol_data: ProtocolData,
    current_epoch: int
) -> Dict[str, Any]:
    platforms = protocol_data["platforms"]
    current_epoch = get_rounded_epoch(current_epoch)

    output_data = {
        "platforms": {},
    }

    web3_service = Web3Service(1, GlobalConstants.get_rpc_url(1))
    gauge_proofs_cache = {}  # Cache for gauge proofs
    user_proofs_cache = {}   # Cache for user proofs

    for chain_id, platform_data in platforms.items():
        platform_address = platform_data["address"]
        block_number = platform_data["latest_setted_block"]

        platform_output = {
            "chain_id": chain_id,
            "platform_address": platform_address,
            "block_data": platform_data["block_data"],
            "gauges": {},
        }

        # Generate gauge controller proof only if not already generated
        if "gauge_controller_proof" not in output_data:
            with console.status("[cyan]Generating gauge controller proof...[/cyan]"):
                gauge_proofs = vm_proofs.get_gauge_proof(
                    protocol=protocol,
                    gauge_address="0x0000000000000000000000000000000000000000",
                    current_epoch=current_epoch,
                    block_number=block_number,
                )
                output_data["gauge_controller_proof"] = (
                    "0x" + gauge_proofs["gauge_controller_proof"].hex()
                )

        with console.status("[magenta]Querying active campaigns...[/magenta]"):
            active_campaigns = query_active_campaigns(
                web3_service, chain_id, platform_address
            )

        # Process all valid gauges for this chain/platform
        unique_gauges = {
            campaign["gauge"].lower() 
            for campaign in active_campaigns 
            if vm_proofs.is_valid_gauge(protocol, campaign["gauge"].lower())
        }

        for gauge_address in unique_gauges:
            if gauge_address not in gauge_proofs_cache:
                console.print(
                    Panel(f"Processing gauge: [magenta]{gauge_address}[/magenta]")
                )
                with console.status("[green]Processing gauge data...[/green]"):
                    gauge_data = await process_gauge(
                        protocol, gauge_address, current_epoch, block_number,
                        user_proofs_cache
                    )
                gauge_proofs_cache[gauge_address] = gauge_data
            
            platform_output["gauges"][gauge_address] = gauge_proofs_cache[gauge_address]

        # Process listed users for each campaign
        for campaign in active_campaigns:
            gauge_address = campaign["gauge"].lower()
            if gauge_address in platform_output["gauges"]:
                with console.status("[cyan]Processing listed users...[/cyan]"):
                    listed_users_data = process_listed_users(
                        protocol,
                        gauge_address,
                        block_number,
                        campaign["listed_users"],
                    )
                platform_output["gauges"][gauge_address]["listed_users"] = listed_users_data

        output_data["platforms"][chain_id] = platform_output

    console.print(f"Finished processing protocol: [blue]{protocol}[/blue]")
    return output_data


async def process_gauge(
    protocol: str, gauge_address: str, current_epoch: int, block_number: int,
    user_proofs_cache: Dict[str, Any]
) -> Dict[str, Any]:
    console.print("Querying votes")
    gauge_votes = await vm_votes.get_gauge_votes(
        protocol, gauge_address, block_number
    )
    console.print(
        f"Found [yellow]{len(gauge_votes)}[/yellow] votes for gauge: [magenta]{gauge_address}[/magenta]"
    )

    console.print("Generating point data proof")
    gauge_proofs = vm_proofs.get_gauge_proof(
        protocol=protocol,
        gauge_address=gauge_address,
        current_epoch=current_epoch,
        block_number=block_number,
    )

    gauge_data = {
        "point_data_proof": "0x" + gauge_proofs["point_data_proof"].hex(),
        "users": {},
    }

    console.print(
        f"Querying eligible users for gauge: [magenta]{gauge_address}[/magenta]"
    )
    eligible_users = await vm_votes.get_eligible_users(
        protocol, gauge_address, current_epoch, block_number
    )
    console.print(
        f"Found [yellow]{len(eligible_users)}[/yellow] eligible users for gauge: [magenta]{gauge_address}[/magenta]"
    )

    for user in eligible_users:
        user_address = user["user"].lower()
        cache_key = f"{gauge_address}:{user_address}"
        
        if cache_key not in user_proofs_cache:
            console.print(
                f"Generating proof for user: [cyan]{user_address}[/cyan]"
            )
            user_proofs = vm_proofs.get_user_proof(
                protocol=protocol,
                gauge_address=gauge_address,
                user=user_address,
                block_number=block_number,
            )
            user_proofs_cache[cache_key] = {
                "storage_proof": "0x" + user_proofs["storage_proof"].hex(),
                "last_vote": user["last_vote"],
                "slope": user["slope"],
                "power": user["power"],
                "end": user["end"],
            }
        
        gauge_data["users"][user_address] = user_proofs_cache[cache_key]

    return gauge_data


def write_protocol_data(
    protocol: str, current_epoch: int, processed_data: Dict[str, Any]
):
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
        "block_data": processed_data["platforms"]["42161"]["block_data"],
        "gauge_controller_proof": processed_data["gauge_controller_proof"],
    }
    with open(os.path.join(protocol_dir, "header.json"), "w") as f:
        json.dump(header_data, f, indent=2)

    # Write main.json (contains all data for the protocol)
    main_data = {
        "epoch": current_epoch,
        "block_data": processed_data["platforms"]["42161"]["block_data"],
        "gauge_controller_proof": processed_data["gauge_controller_proof"],
        "platforms": processed_data["platforms"],
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
            gauge_file = os.path.join(
                platform_dir, f"{gauge_address.lower()}.json"
            )
            with open(gauge_file, "w") as f:
                json.dump(gauge_data, f, indent=2)

    console.print(f"Saved data for [blue]{protocol}[/blue] in {protocol_dir}")


def process_listed_users(
    protocol: str,
    gauge_address: str,
    block_number: int,
    listed_users: List[str],
) -> Dict[str, Any]:
    listed_users_data = {}
    for listed_user in listed_users:
        console.print(
            f"Generating proof for listed user: [cyan]{listed_user}[/cyan]"
        )
        user_proofs = vm_proofs.get_user_proof(
            protocol=protocol,
            gauge_address=gauge_address,
            user=listed_user,
            block_number=block_number,
        )
        listed_users_data[listed_user.lower()] = {
            "storage_proof": "0x" + user_proofs["storage_proof"].hex(),
        }
    return listed_users_data


async def main(all_protocols_data: AllProtocolsData, current_epoch: int):
    """
    Main function to process all protocols and generate active proofs.

    Args:
        all_protocols_data (AllProtocolsData): Data containing all protocols and platforms.
        current_epoch (int): The current voting epoch.
    """
    console.print(
        f"Starting active proofs generation for epoch: [yellow]{current_epoch}[/yellow]"
    )

    for protocol, protocol_data in all_protocols_data["protocols"].items():
        if len(protocol_data["platforms"]) == 0:
            console.print(
                f"Skipping protocol: [blue]{protocol}[/blue] as no platforms found"
            )
            continue
        console.print(f"Processing protocol: [blue]{protocol}[/blue]")
        processed_data = await process_protocol(protocol, protocol_data, current_epoch)
        write_protocol_data(protocol.lower(), current_epoch, processed_data)

    console.print(
        "[bold green]Finished generating active proofs for all protocols[/bold green]"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate active proofs for protocols"
    )
    parser.add_argument(
        "all_platforms_file",
        type=str,
        help="Path to the JSON file containing all platforms data",
    )
    parser.add_argument(
        "current_epoch", type=int, help="Current epoch timestamp"
    )

    args = parser.parse_args()

    with open(args.all_platforms_file, "r") as f:
        all_protocols_data = json.load(f)

    asyncio.run(main(all_protocols_data, args.current_epoch))
    console.print(
        "[bold green]Active proofs generation script completed[/bold green]"
    )
