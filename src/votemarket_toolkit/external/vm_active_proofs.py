"""
Process a protocol to generate active proofs.

This version handles multiple platforms on the same chain by merging gauge data into a single output.
For each chain, the final folder structure is:
  protocol/chainId/
    header.json   --> common header for the chain
    index.json    --> contains all merged gauge data
    <gauge_address>.json   --> one file per gauge (same as its entry in index)

Each gauge in index.json has the structure:
{
  "point_data_proof": "...",
  "users": { ... },
  "platforms": {
    "0xPlatformAddress1": {
      "active_campaigns_ids": [ ... ],
      "listed_users": {
         "campaignId": { ... }
      }
    },
    "0xPlatformAddress2": { ... }
  }
}
"""

import argparse
import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from votemarket_toolkit.campaigns.services.campaign_service import CampaignService
from votemarket_toolkit.campaigns.services.data_service import VoteMarketDataService
from votemarket_toolkit.proofs import VoteMarketProofs
from votemarket_toolkit.shared.types import AllProtocolsData, ProtocolData
from votemarket_toolkit.utils import get_rounded_epoch
from votemarket_toolkit.votes.services.votes_service import votes_service

load_dotenv()

TEMP_DIR = "temp"

# Initialize services
campaign_service = CampaignService()
vm_proofs = VoteMarketProofs(1)
vm_votes = VoteMarketDataService(1)
console = Console()


def is_campaign_active(campaign: dict) -> bool:
    """Check if a campaign is active and should be processed."""
    current_timestamp = int(datetime.now().timestamp())
    return (
        not campaign["is_closed"]
        and campaign["details"]["end_timestamp"] > current_timestamp
        and campaign["period_left"] > 0
    )


async def process_protocol(
    protocol: str, protocol_data: ProtocolData, current_epoch: int
) -> Dict[str, Any]:
    """
    Process each protocol by chain, merging gauge data from all platforms.

    Output structure:
    {
      "chains": { chain_id: { block_data, gauge_controller_proof } },
      "gauges": { chain_id: { gauge_address: { point_data_proof, users, platforms } } }
    }
    """
    platforms_by_chain = protocol_data["platforms"]
    current_epoch = get_rounded_epoch(current_epoch)

    output_data = {
        "chains": {},
        "gauges": {}
    }

    # Cache for gauges & users to avoid duplicate processing
    gauge_proofs_cache: Dict[str, Dict[str, Any]] = {}
    user_proofs_cache: Dict[str, Dict[str, Any]] = {}

    for chain_id, platforms_list in platforms_by_chain.items():
        # Initialize chain-level output
        if chain_id not in output_data["chains"]:
            output_data["chains"][chain_id] = {
                "block_data": None,
                "gauge_controller_proof": None,
            }
        if chain_id not in output_data["gauges"]:
            output_data["gauges"][chain_id] = {}

        chain_output = output_data["chains"][chain_id]

        # Use the first platform's block_data and block number as the chain-level reference
        if len(platforms_list) > 0:
            chain_output["block_data"] = platforms_list[0]["block_data"]
            block_number = platforms_list[0]["latest_setted_block"]

            if chain_output["gauge_controller_proof"] is None:
                with console.status(
                    f"[cyan]Generating gauge controller proof for chain {chain_id}...[/cyan]"
                ):
                    gauge_proofs = vm_proofs.get_gauge_proof(
                        protocol=protocol,
                        gauge_address="0x0000000000000000000000000000000000000000",
                        current_epoch=current_epoch,
                        block_number=block_number,
                    )
                    chain_output["gauge_controller_proof"] = (
                        "0x" + gauge_proofs["gauge_controller_proof"].hex()
                    )

        # Process each platform on the chain
        for platform_data in platforms_list:
            platform_address = platform_data["address"]
            block_number = platform_data["latest_setted_block"]

            with console.status(
                f"[magenta]Querying active campaigns for platform {platform_address} on chain {chain_id}...[/magenta]"
            ):
                campaign_svc = CampaignService()
                all_campaigns = await campaign_svc.query_active_campaigns(
                    chain_id, platform_address
                )
                active_campaigns = [
                    campaign for campaign in all_campaigns if is_campaign_active(campaign)
                ]
                if len(active_campaigns) < len(all_campaigns):
                    console.print(
                        f"[yellow]Filtered out {len(all_campaigns) - len(active_campaigns)} inactive campaigns for platform {platform_address}[/yellow]"
                    )

            # Process each active campaign for this platform
            for campaign in active_campaigns:
                gauge_address = campaign["gauge"].lower()
                if not vm_proofs.is_valid_gauge(protocol, gauge_address):
                    continue

                # Process gauge if it hasn't been processed already (common for the protocol)
                if gauge_address not in gauge_proofs_cache:
                    console.print(
                        Panel(f"Processing gauge: [magenta]{gauge_address}[/magenta]")
                    )
                    with console.status("[green]Processing gauge data...[/green]"):
                        gauge_data = await process_gauge(
                            protocol,
                            gauge_address,
                            current_epoch,
                            block_number,
                            user_proofs_cache,
                        )
                    # Initialize a container for per-platform campaign data
                    gauge_data["platforms"] = {}
                    gauge_proofs_cache[gauge_address] = gauge_data
                else:
                    gauge_data = gauge_proofs_cache[gauge_address]

                # Update the platform-specific section for this gauge
                platform_section = gauge_data["platforms"].get(
                    platform_address, {"active_campaigns_ids": [], "listed_users": {}}
                )
                if campaign["id"] not in platform_section["active_campaigns_ids"]:
                    platform_section["active_campaigns_ids"].append(campaign["id"])

                with console.status(
                    f"[cyan]Processing listed users for campaign {campaign['id']} on platform {platform_address}...[/cyan]"
                ):
                    listed_users_data = process_listed_users(
                        protocol,
                        gauge_address,
                        block_number,
                        campaign["listed_users"],
                    )
                # Associate listed users with the campaign id (as a string)
                platform_section["listed_users"][str(campaign["id"])] = listed_users_data
                gauge_data["platforms"][platform_address] = platform_section

                # Merge gauge data into the chain-level gauges structure
                if gauge_address not in output_data["gauges"][chain_id]:
                    output_data["gauges"][chain_id][gauge_address] = gauge_data
                else:
                    # Merge platform-specific data if gauge already exists
                    existing_platforms = output_data["gauges"][chain_id][gauge_address]["platforms"]
                    for plat_addr, plat_data in gauge_data["platforms"].items():
                        if plat_addr not in existing_platforms:
                            existing_platforms[plat_addr] = plat_data
                        else:
                            for cid in plat_data["active_campaigns_ids"]:
                                if cid not in existing_platforms[plat_addr]["active_campaigns_ids"]:
                                    existing_platforms[plat_addr]["active_campaigns_ids"].append(cid)
                            existing_platforms[plat_addr]["listed_users"].update(plat_data["listed_users"])

        console.print(f"Finished processing chain {chain_id} for protocol: [blue]{protocol}[/blue]")

    return output_data


async def process_gauge(
    protocol: str,
    gauge_address: str,
    current_epoch: int,
    block_number: int,
    user_proofs_cache: Dict[str, Any],
) -> Dict[str, Any]:
    console.print("Querying votes")
    gauge_votes = await votes_service.get_gauge_votes(
        protocol, gauge_address, block_number
    )
    console.print(
        f"Found [yellow]{len(gauge_votes.votes)}[/yellow] votes for gauge: [magenta]{gauge_address}[/magenta]"
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


def process_listed_users(
    protocol: str,
    gauge_address: str,
    block_number: int,
    listed_users: List[str],
) -> Dict[str, Any]:
    """
    Process the listed users for a campaign. For each listed user, generate a storage proof.
    """
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


def write_protocol_data(
    protocol: str, current_epoch: int, processed_data: Dict[str, Any]
):
    """
    Write processed protocol data to a single folder per chain.
    Structure: protocol/chainId/header.json, protocol/chainId/index.json,
               and one file per gauge (protocol/chainId/<gauge_address>.json)
    """
    protocol_dir = os.path.join(TEMP_DIR, protocol.lower())
    os.makedirs(protocol_dir, exist_ok=True)

    for chain_id, chain_data in processed_data["chains"].items():
        chain_dir = os.path.join(protocol_dir, chain_id)
        os.makedirs(chain_dir, exist_ok=True)

        # Write header.json (common header for the chain)
        header_data = {
            "epoch": current_epoch,
            "block_data": chain_data["block_data"],
            "gauge_controller_proof": chain_data["gauge_controller_proof"],
        }
        with open(os.path.join(chain_dir, "header.json"), "w") as f:
            json.dump(header_data, f, indent=2)

        # Write index.json containing merged gauge data
        index_data = {
            "epoch": current_epoch,
            "block_data": chain_data["block_data"],
            "gauge_controller_proof": chain_data["gauge_controller_proof"],
            "gauges": processed_data["gauges"].get(chain_id, {}),
        }
        with open(os.path.join(chain_dir, "index.json"), "w") as f:
            json.dump(index_data, f, indent=2)

        # Write one file per gauge
        for gauge_address, gauge_data in processed_data["gauges"].get(chain_id, {}).items():
            gauge_file = os.path.join(chain_dir, f"{gauge_address.lower()}.json")
            with open(gauge_file, "w") as f:
                json.dump(gauge_data, f, indent=2)

        console.print(f"Saved data for chain [blue]{chain_id}[/blue] in {chain_dir}")


async def main(all_protocols_data: AllProtocolsData, current_epoch: int):
    """
    Main function to process all protocols and generate active proofs.
    """
    console.print(
        "Starting active proofs generation for epoch: [yellow]"
        f"{current_epoch}[/yellow]"
    )
    for protocol, protocol_data in all_protocols_data["protocols"].items():
        if len(protocol_data["platforms"]) == 0:
            console.print(
                f"Skipping protocol: [blue]{protocol}[/blue] as no platforms found"
            )
            continue
        console.print(f"Processing protocol: [blue]{protocol}[/blue]")
        processed_data = await process_protocol(
            protocol, protocol_data, current_epoch
        )
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
