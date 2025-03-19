"""
Process a protocol to generate active proofs.

This version handles multiple platforms on the same chain by using only the first (representative)
platform’s data for chain-level information. The final folder structure is:

  TEMP_DIR/<protocol>/
      header.json       --> Contains protocol-level header data (epoch, block_data, gauge_controller_proof)
      index.json        --> Contains all protocol data with a "platforms" object:
                           {
                             "42161": {
                               "chain_id": "42161",
                               "platform_address": "...",
                               "block_data": { ... },
                               "gauges": { ... }
                             },
                             ...
                           }
      <chain_id>/       --> For each chain, a folder is created containing gauge files:
                             <gauge_address>.json   --> One file per gauge in that chain
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
    Process each chain for the protocol.
    
    For each chain, use the first platform's data as the representative.
    
    Returns a dictionary with:
      - "chains": a dict keyed by chain_id with header data
      - "gauges": merged gauges per chain
    """
    # platforms_by_chain is a dict where keys are chain ids and values are lists of platform dicts.
    platforms_by_chain = protocol_data["platforms"]
    current_epoch = get_rounded_epoch(current_epoch)

    output_data: Dict[str, Any] = {"chains": {}, "gauges": {}}

    # Global caches
    gauge_proofs_cache: Dict[str, Dict[str, Any]] = {}
    user_proofs_cache: Dict[str, Dict[str, Any]] = {}

    for chain_id, platforms_list in platforms_by_chain.items():
        if not platforms_list:
            continue
        # Use only the first platform's data for chain-level info
        rep_platform = platforms_list[0]
        block_number = rep_platform["latest_setted_block"]

        # Store chain header (representative) data
        output_data["chains"][chain_id] = {
            "chain_id": chain_id,
            "platform_address": rep_platform["address"],
            "block_data": rep_platform["block_data"],
            "gauge_controller_proof": None,
        }
        # Initialize gauges container for this chain
        output_data["gauges"][chain_id] = {}

        # Generate gauge controller proof using the representative platform's block number
        with console.status(f"[cyan]Generating gauge controller proof for chain {chain_id}...[/cyan]"):
            gauge_proofs = vm_proofs.get_gauge_proof(
                protocol=protocol,
                gauge_address="0x0000000000000000000000000000000000000000",
                current_epoch=current_epoch,
                block_number=block_number,
            )
            output_data["chains"][chain_id]["gauge_controller_proof"] = "0x" + gauge_proofs["gauge_controller_proof"].hex()

        # Process each platform in the chain (if needed for gauges, but we merge results)
        for platform_data in platforms_list:
            platform_address = platform_data["address"]
            block_number = platform_data["latest_setted_block"]

            with console.status(f"[magenta]Querying active campaigns for platform {platform_address} on chain {chain_id}...[/magenta]"):
                campaign_svc = CampaignService()
                all_campaigns = await campaign_svc.query_active_campaigns(chain_id, platform_address)
                active_campaigns = [c for c in all_campaigns if is_campaign_active(c)]
                if len(active_campaigns) < len(all_campaigns):
                    console.print(f"[yellow]Filtered out {len(all_campaigns) - len(active_campaigns)} inactive campaigns for platform {platform_address}[/yellow]")

            # Process each active campaign
            for campaign in active_campaigns:
                gauge_address = campaign["gauge"].lower()
                if not vm_proofs.is_valid_gauge(protocol, gauge_address):
                    continue

                if gauge_address not in gauge_proofs_cache:
                    console.print(Panel(f"Processing gauge: [magenta]{gauge_address}[/magenta]"))
                    with console.status("[green]Processing gauge data...[/green]"):
                        gauge_data = await process_gauge(
                            protocol,
                            gauge_address,
                            current_epoch,
                            block_number,
                            user_proofs_cache,
                        )
                    # Initialize per-platform container for gauge data
                    gauge_data["platforms"] = {}
                    gauge_proofs_cache[gauge_address] = gauge_data
                else:
                    gauge_data = gauge_proofs_cache[gauge_address]

                # Update platform-specific data for this gauge
                platform_section = gauge_data["platforms"].get(
                    platform_address, {"active_campaigns_ids": [], "listed_users": {}}
                )
                if campaign["id"] not in platform_section["active_campaigns_ids"]:
                    platform_section["active_campaigns_ids"].append(campaign["id"])
                with console.status(f"[cyan]Processing listed users for campaign {campaign['id']} on {platform_address}...[/cyan]"):
                    listed_users_data = process_listed_users(protocol, gauge_address, block_number, campaign["listed_users"])
                platform_section["listed_users"][str(campaign["id"])] = listed_users_data
                gauge_data["platforms"][platform_address] = platform_section

                # Merge gauge data into chain-level gauges
                if gauge_address not in output_data["gauges"][chain_id]:
                    output_data["gauges"][chain_id][gauge_address] = gauge_data
                else:
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
    console.print(f"Querying votes for gauge: [magenta]{gauge_address}[/magenta]")
    gauge_votes = await votes_service.get_gauge_votes(protocol, gauge_address, block_number)
    console.print(f"Found [yellow]{len(gauge_votes.votes)}[/yellow] votes for gauge: [magenta]{gauge_address}[/magenta]")

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

    console.print(f"Querying eligible users for gauge: [magenta]{gauge_address}[/magenta]")
    eligible_users = await vm_votes.get_eligible_users(protocol, gauge_address, current_epoch, block_number)
    console.print(f"Found [yellow]{len(eligible_users)}[/yellow] eligible users for gauge: [magenta]{gauge_address}[/magenta]")

    for user in eligible_users:
        user_address = user["user"].lower()
        cache_key = f"{gauge_address}:{user_address}"
        if cache_key not in user_proofs_cache:
            console.print(f"Generating proof for user: [cyan]{user_address}[/cyan]")
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
    Process the listed users for a campaign.
    For each listed user, generate a storage proof.
    """
    listed_users_data = {}
    for listed_user in listed_users:
        console.print(f"Generating proof for listed user: [cyan]{listed_user}[/cyan]")
        user_proofs = vm_proofs.get_user_proof(
            protocol=protocol,
            gauge_address=gauge_address,
            user=listed_user,
            block_number=block_number,
        )
        listed_users_data[listed_user.lower()] = {
            "storage_proof": "0x" + user_proofs["storage_proof"].hex()
        }
    return listed_users_data


def write_protocol_data(protocol: str, current_epoch: int, processed_data: Dict[str, Any]):
    """
    Write processed protocol data to files.
    
    New folder structure:
      TEMP_DIR/<protocol>/ 
         header.json       --> Contains protocol-level header data (from a representative chain)
         index.json        --> Contains all protocol data with a "platforms" object,
                             where each chain id maps to an object with:
                               chain_id, platform_address, block_data, and gauges.
         <chain_id>/       --> For each chain, a folder is created containing gauge files:
                              <gauge_address>.json   --> One file per gauge for that chain.
    """
    protocol_dir = os.path.join(TEMP_DIR, protocol.lower())
    os.makedirs(protocol_dir, exist_ok=True)

    # For header.json and index.json, pick a representative chain.
    # Here we choose chain "42161" if available; otherwise, use the first chain.
    rep_chain_id = "42161" if "42161" in processed_data["chains"] else next(iter(processed_data["chains"]))
    rep_chain = processed_data["chains"][rep_chain_id]

    header_data = {
        "epoch": current_epoch,
        "block_data": rep_chain["block_data"],
        "gauge_controller_proof": rep_chain["gauge_controller_proof"]
    }
    with open(os.path.join(protocol_dir, "header.json"), "w") as f:
        json.dump(header_data, f, indent=2)

    # Build a platforms dictionary from chain headers and gauges (without duplication)
    merged_platforms = {}
    for chain_id, chain_header in processed_data["chains"].items():
        merged_platforms[chain_id] = {
            "chain_id": chain_id,
            "platform_address": chain_header["platform_address"],
            "block_data": chain_header["block_data"],
            "gauges": processed_data["gauges"].get(chain_id, {})
        }

    index_data = {
        "epoch": current_epoch,
        "block_data": rep_chain["block_data"],
        "gauge_controller_proof": rep_chain["gauge_controller_proof"],
        "platforms": merged_platforms
    }
    with open(os.path.join(protocol_dir, "index.json"), "w") as f:
        json.dump(index_data, f, indent=2)

    # For each chain, create a subfolder for gauge files and write them.
    for chain_id, chain_info in merged_platforms.items():
        chain_folder = os.path.join(protocol_dir, chain_id)
        os.makedirs(chain_folder, exist_ok=True)
        for gauge_address, gauge_data in chain_info["gauges"].items():
            gauge_file = os.path.join(chain_folder, f"{gauge_address.lower()}.json")
            with open(gauge_file, "w") as f:
                json.dump(gauge_data, f, indent=2)
        console.print(f"Saved gauge files for chain [blue]{chain_id}[/blue] in {chain_folder}")


async def main(all_protocols_data: AllProtocolsData, current_epoch: int):
    console.print(f"Starting active proofs generation for epoch: [yellow]{current_epoch}[/yellow]")
    for protocol, protocol_data in all_protocols_data["protocols"].items():
        if not protocol_data["platforms"]:
            console.print(f"Skipping protocol: [blue]{protocol}[/blue] as no platforms found")
            continue
        console.print(f"Processing protocol: [blue]{protocol}[/blue]")
        processed_data = await process_protocol(protocol, protocol_data, current_epoch)
        write_protocol_data(protocol.lower(), current_epoch, processed_data)
    console.print("[bold green]Finished generating active proofs for all protocols[/bold green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate active proofs for protocols")
    parser.add_argument("all_platforms_file", type=str, help="Path to the JSON file containing all platforms data")
    parser.add_argument("current_epoch", type=int, help="Current epoch timestamp")
    args = parser.parse_args()

    with open(args.all_platforms_file, "r") as f:
        all_protocols_data = json.load(f)

    asyncio.run(main(all_protocols_data, args.current_epoch))
    console.print("[bold green]Active proofs generation script completed[/bold green]")