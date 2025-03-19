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
console = Console()

# Initialize services
campaign_service = CampaignService()
vm_proofs = VoteMarketProofs(1)
vm_votes = VoteMarketDataService(1)


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
    
    For each chain we use the first (representative) platform’s data for chain-level info.
    Returns a dict with:
      - "chains": dict keyed by chain_id containing header data.
      - "platforms": dict keyed by chain_id, each is a dict keyed by platform address with its gauge data.
    """
    platforms_by_chain = protocol_data["platforms"]  # chain_id -> list of platform dicts
    current_epoch = get_rounded_epoch(current_epoch)
    output_data: Dict[str, Any] = {"chains": {}, "platforms": {}}

    # Global caches
    gauge_proofs_cache: Dict[str, Dict[str, Any]] = {}
    user_proofs_cache: Dict[str, Dict[str, Any]] = {}

    for chain_id, platforms_list in platforms_by_chain.items():
        if not platforms_list:
            continue
        # Use the first platform's data as representative
        rep_platform = platforms_list[0]
        block_number = rep_platform["latest_setted_block"]

        output_data["chains"][chain_id] = {
            "chain_id": chain_id,
            "platform_address": rep_platform["address"],
            "block_data": rep_platform["block_data"],
            "gauge_controller_proof": None,
        }
        output_data["platforms"][chain_id] = {}

        with console.status(f"[cyan]Generating gauge controller proof for chain {chain_id}...[/cyan]"):
            gauge_proofs = vm_proofs.get_gauge_proof(
                protocol=protocol,
                gauge_address="0x0000000000000000000000000000000000000000",
                current_epoch=current_epoch,
                block_number=block_number,
            )
            output_data["chains"][chain_id]["gauge_controller_proof"] = "0x" + gauge_proofs["gauge_controller_proof"].hex()

        # Process each platform for this chain
        for platform_data in platforms_list:
            platform_address = platform_data["address"]
            block_number = platform_data["latest_setted_block"]

            # Initialize platform-specific structure under this chain.
            if platform_address not in output_data["platforms"][chain_id]:
                output_data["platforms"][chain_id][platform_address] = {
                    "block_data": platform_data["block_data"],
                    "active_campaigns": [],
                    "gauges": {},
                }

            platform_output = output_data["platforms"][chain_id][platform_address]

            with console.status(f"[magenta]Querying active campaigns for platform {platform_address} on chain {chain_id}...[/magenta]"):
                campaign_svc = CampaignService()
                all_campaigns = await campaign_svc.query_active_campaigns(chain_id, platform_address)
                active_campaigns = [c for c in all_campaigns if is_campaign_active(c)]
                if len(active_campaigns) < len(all_campaigns):
                    console.print(f"[yellow]Filtered out {len(all_campaigns) - len(active_campaigns)} inactive campaigns for platform {platform_address}[/yellow]")

                # Here we store composite keys in the platform-level active_campaigns list.
                for campaign in active_campaigns:
                    composite_campaign_id = f"{platform_address.lower()}-{campaign['id']}"
                    if composite_campaign_id not in platform_output["active_campaigns"]:
                        platform_output["active_campaigns"].append(composite_campaign_id)

            for campaign in active_campaigns:
                gauge_address = campaign["gauge"].lower()
                if not vm_proofs.is_valid_gauge(protocol, gauge_address):
                    continue

                composite_campaign_id = f"{platform_address.lower()}-{campaign['id']}"
                # Process gauge if not already processed
                if gauge_address not in gauge_proofs_cache:
                    console.print(Panel(f"Processing gauge: [magenta]{gauge_address}[/magenta] on {platform_address}"))
                    with console.status("[green]Processing gauge data...[/green]"):
                        gauge_data = await process_gauge(
                            protocol,
                            gauge_address,
                            current_epoch,
                            block_number,
                            user_proofs_cache,
                        )
                    # Store campaign info directly on gauge_data (no inner "platforms" key)
                    gauge_data["active_campaigns_ids"] = [composite_campaign_id]
                    gauge_data["listed_users"] = {composite_campaign_id: process_listed_users(
                        protocol, gauge_address, block_number, campaign["listed_users"]
                    )}
                    gauge_proofs_cache[gauge_address] = gauge_data
                else:
                    gauge_data = gauge_proofs_cache[gauge_address]
                    if composite_campaign_id not in gauge_data.get("active_campaigns_ids", []):
                        gauge_data.setdefault("active_campaigns_ids", []).append(composite_campaign_id)
                    gauge_data.setdefault("listed_users", {})[composite_campaign_id] = process_listed_users(
                        protocol, gauge_address, block_number, campaign["listed_users"]
                    )

                # Save gauge data for this platform under the chain.
                output_data["platforms"][chain_id][platform_address]["gauges"][gauge_address] = gauge_data

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
    Write processed protocol data to files using the new folder structure:
    
    Desired folder structure:
      TEMP_DIR/<protocol>/
          <platform_address>/ 
              <chain_id>/
                  header.json       --> Contains chain-level header data (from the representative platform for that chain)
                  index.json        --> Contains chain data for that platform
                  <gauge_address>.json  --> One file per gauge for that chain & platform
    """
    protocol_dir = os.path.join(TEMP_DIR, protocol.lower())
    os.makedirs(protocol_dir, exist_ok=True)

    # First, re-organize processed_data["platforms"] (keyed by chain id and then by platform) 
    # into a new dict keyed by platform address.
    platforms_by_address: Dict[str, Dict[str, Any]] = {}
    for chain_id, chain_platforms in processed_data["platforms"].items():
        for platform_addr, platform_data in chain_platforms.items():
            if platform_addr not in platforms_by_address:
                platforms_by_address[platform_addr] = {}
            platforms_by_address[platform_addr][chain_id] = platform_data

    # For header.json at protocol level, we choose a representative chain from one of the platforms.
    # Here, we arbitrarily pick the first platform and the first chain within it.
    rep_platform_addr = next(iter(platforms_by_address))
    rep_chain_id = next(iter(platforms_by_address[rep_platform_addr]))
    rep_platform = platforms_by_address[rep_platform_addr][rep_chain_id]
    # Note: We use the chain header from processed_data["chains"] for block_data and gauge_controller_proof.
    rep_chain_header = processed_data["chains"].get(rep_chain_id, {})

    header_data = {
        "epoch": current_epoch,
        "block_data": rep_chain_header.get("block_data", {}),
        "gauge_controller_proof": rep_chain_header.get("gauge_controller_proof", "")
    }
    with open(os.path.join(protocol_dir, "header.json"), "w") as f:
        json.dump(header_data, f, indent=2)

    # Build index.json structure: key "platforms" now is keyed by platform address, then by chain id.
    index_platforms = {}
    for platform_addr, chains in platforms_by_address.items():
        index_platforms[platform_addr] = {}
        for chain_id, platform_data in chains.items():
            # For each chain on a given platform, merge with chain-level header data.
            index_platforms[platform_addr][chain_id] = {
                "chain_id": chain_id,
                "platform_address": platform_addr,
                "block_data": processed_data["chains"].get(chain_id, {}).get("block_data", {}),
                "gauges": platform_data.get("gauges", {}),
                "active_campaigns": platform_data.get("active_campaigns", [])
            }
    index_data = {
        "epoch": current_epoch,
        "block_data": rep_chain_header.get("block_data", {}),
        "gauge_controller_proof": rep_chain_header.get("gauge_controller_proof", ""),
        "platforms": index_platforms
    }
    with open(os.path.join(protocol_dir, "index.json"), "w") as f:
        json.dump(index_data, f, indent=2)

    # Now, for each platform address, create a folder and under it, a subfolder per chain.
    for platform_addr, chains in index_platforms.items():
        platform_folder = os.path.join(protocol_dir, platform_addr.lower())
        os.makedirs(platform_folder, exist_ok=True)
        for chain_id, chain_info in chains.items():
            chain_folder = os.path.join(platform_folder, chain_id)
            os.makedirs(chain_folder, exist_ok=True)
            # Write chain-level header and index for this platform
            with open(os.path.join(chain_folder, "header.json"), "w") as f:
                json.dump({
                    "epoch": current_epoch,
                    "block_data": chain_info["block_data"],
                    "gauge_controller_proof": chain_info.get("gauge_controller_proof", "")
                }, f, indent=2)
            with open(os.path.join(chain_folder, "index.json"), "w") as f:
                json.dump(chain_info, f, indent=2)
            # Write individual gauge files
            for gauge_address, gauge_data in chain_info["gauges"].items():
                gauge_file = os.path.join(chain_folder, f"{gauge_address.lower()}.json")
                with open(gauge_file, "w") as f:
                    json.dump(gauge_data, f, indent=2)
            console.print(f"Saved gauge files for platform [cyan]{platform_addr}[/cyan] on chain [blue]{chain_id}[/blue] in {chain_folder}")


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
    import sys
    parser = argparse.ArgumentParser(description="Generate active proofs for protocols")
    parser.add_argument("all_platforms_file", type=str, help="Path to the JSON file containing all platforms data")
    parser.add_argument("current_epoch", type=int, help="Current epoch timestamp")
    args = parser.parse_args()

    with open(args.all_platforms_file, "r") as f:
        all_protocols_data = json.load(f)

    asyncio.run(main(all_protocols_data, args.current_epoch))
    console.print("[bold green]Active proofs generation script completed[/bold green]")
