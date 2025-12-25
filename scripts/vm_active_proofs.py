import argparse
import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from votemarket_toolkit.campaigns import CampaignService
from votemarket_toolkit.data import EligibilityService
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
vm_eligibility = EligibilityService(1)


def is_campaign_active(campaign: dict) -> bool:
    """
    Check if a campaign should be processed for proof generation.

    A campaign should be included if:
    1. It's currently active (end_timestamp > now AND has remaining_periods)
    2. OR it ended within the current epoch (same week) - because we still need
       proofs for votes cast during this epoch

    This ensures campaigns that ended today or this week still generate proofs,
    allowing users to claim rewards for the current epoch's voting period.
    """
    current_timestamp = int(datetime.now().timestamp())
    current_epoch = get_rounded_epoch(current_timestamp)

    is_closed = campaign.get("is_closed", False)
    end_timestamp = campaign["campaign"]["end_timestamp"]
    end_epoch = get_rounded_epoch(end_timestamp)
    remaining_periods = campaign.get("remaining_periods", 0)

    # Campaign is active if it's not closed AND either:
    # 1. Still running (end_timestamp in future with remaining periods)
    # 2. Ended within current epoch (same week - proofs still needed)
    is_active = not is_closed and (
        (end_timestamp > current_timestamp and remaining_periods > 0)
        or (end_epoch == current_epoch)
    )

    return is_active


async def process_gauge(
    protocol: str,
    gauge_address: str,
    current_epoch: int,
    block_number: int,
    user_proofs_cache: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a gauge by generating its proof and gathering vote details.

    Returns:
      - gauge_proof_data: containing proofs (e.g. point_data_proof and storage proofs for each user).
      - gauge_vote_data: containing only the raw vote details for each eligible user.
    """
    console.print(
        f"Querying votes for gauge: [magenta]{gauge_address}[/magenta]"
    )
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
    gauge_proof_data = {
        "point_data_proof": "0x" + gauge_proofs["point_data_proof"].hex(),
        "users": {},
    }
    gauge_vote_data = {"users": {}}

    console.print(
        f"Querying eligible users for gauge: [magenta]{gauge_address}[/magenta]"
    )
    eligible_users = await vm_eligibility.get_eligible_users(
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
        proof_info = user_proofs_cache[cache_key]
        # In gauge proofs, only include the storage proof.
        gauge_proof_data["users"][user_address] = {
            "storage_proof": proof_info["storage_proof"]
        }
        # In vote data, include only the raw vote details.
        gauge_vote_data["users"][user_address] = {
            "last_vote": proof_info["last_vote"],
            "slope": proof_info["slope"],
            "power": proof_info["power"],
            "end": proof_info["end"],
        }
    return gauge_proof_data, gauge_vote_data


def process_listed_users(
    protocol: str,
    gauge_address: str,
    block_number: int,
    listed_users: List[str],
) -> Dict[str, Any]:
    """
    Process the listed users for a campaign by generating a storage proof.
    (Listed users do not include raw vote details.)
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
            "storage_proof": "0x" + user_proofs["storage_proof"].hex()
        }
    return listed_users_data


async def process_protocol(
    protocol: str, protocol_data: ProtocolData, current_epoch: int
) -> Dict[str, Any]:
    """
    Process each chain for the protocol and generate parallel structures:
      - "platforms": for proofs (stored in index/gauge files)
      - "votes": for raw vote details only (to be stored in a separate file)
    """
    platforms_by_chain = protocol_data[
        "platforms"
    ]  # chain_id -> list of platform dicts
    current_epoch = get_rounded_epoch(current_epoch)
    output_data: Dict[str, Any] = {"chains": {}, "platforms": {}}
    output_data["votes"] = {}  # Separate vote details

    # Global caches for gauge proofs and vote details.
    gauge_proofs_cache: Dict[str, Dict[str, Any]] = {}
    gauge_votes_cache: Dict[str, Dict[str, Any]] = {}
    user_proofs_cache: Dict[str, Dict[str, Any]] = {}

    for chain_id, platforms_list in platforms_by_chain.items():
        if not platforms_list:
            continue

        # Use the first platform’s data as representative.
        rep_platform = platforms_list[0]
        block_number = rep_platform["latest_setted_block"]

        output_data["chains"][chain_id] = {
            "chain_id": chain_id,
            "platform_address": rep_platform["address"],
            "block_data": rep_platform["block_data"],
            "gauge_controller_proof": None,
        }
        output_data["platforms"][chain_id] = {}
        output_data["votes"].setdefault(chain_id, {})

        with console.status(
            f"[cyan]Generating gauge controller proof for chain {chain_id}...[/cyan]"
        ):
            gauge_controller = vm_proofs.get_gauge_proof(
                protocol=protocol,
                gauge_address="0x0000000000000000000000000000000000000000",
                current_epoch=current_epoch,
                block_number=block_number,
            )
            output_data["chains"][chain_id]["gauge_controller_proof"] = (
                "0x" + gauge_controller["gauge_controller_proof"].hex()
            )

        # Process each platform for this chain.
        for platform_data in platforms_list:
            platform_address = platform_data["address"]
            block_number = platform_data["latest_setted_block"]

            if platform_address not in output_data["platforms"][chain_id]:
                output_data["platforms"][chain_id][platform_address] = {
                    "block_data": platform_data["block_data"],
                    "gauges": {},
                }
            if platform_address not in output_data["votes"][chain_id]:
                output_data["votes"][chain_id][platform_address] = {
                    "gauges": {},
                }

            # Query active campaigns (used to process gauges) but do not store globally.
            with console.status(
                f"[magenta]Querying active campaigns for platform {platform_address} on chain {chain_id}...[/magenta]"
            ):
                campaign_svc = CampaignService()
                all_campaigns = await campaign_svc.get_campaigns(
                    chain_id, platform_address
                )
                active_campaigns = [
                    c for c in all_campaigns if is_campaign_active(c)
                ]
                if len(active_campaigns) < len(all_campaigns):
                    console.print(
                        f"[yellow]Filtered out {len(all_campaigns) - len(active_campaigns)} inactive campaigns for platform {platform_address}[/yellow]"
                    )

            # Process each campaign for the platform.
            for campaign in active_campaigns:
                # Get gauge and addresses from campaign structure
                gauge_address = campaign["campaign"]["gauge"].lower()
                listed_users = campaign.get("addresses", [])

                # Validate gauge with detailed logging
                validation_result = vm_proofs.validate_gauge(protocol, gauge_address)
                if validation_result.success and validation_result.data:
                    gauge_validation = validation_result.data
                    if not gauge_validation.is_valid:
                        console.print(
                            f"[yellow]Skipping campaign {campaign['id']} - gauge {gauge_address} "
                            f"failed validation: {gauge_validation.reason}[/yellow]"
                        )
                        continue
                elif not validation_result.success:
                    error_msg = validation_result.errors[0].message if validation_result.errors else "Unknown error"
                    console.print(
                        f"[red]Skipping campaign {campaign['id']} - gauge validation error: "
                        f"{error_msg}[/red]"
                    )
                    continue

                composite_campaign_id = (
                    f"{platform_address.lower()}-{campaign['id']}"
                )
                if gauge_address not in gauge_proofs_cache:
                    console.print(
                        Panel(
                            f"Processing gauge: [magenta]{gauge_address}[/magenta] on {platform_address}"
                        )
                    )
                    with console.status(
                        "[green]Processing gauge data...[/green]"
                    ):
                        (
                            gauge_proof_data,
                            gauge_vote_data,
                        ) = await process_gauge(
                            protocol,
                            gauge_address,
                            current_epoch,
                            block_number,
                            user_proofs_cache,
                        )
                    # For proofs, store campaign IDs and listed users per gauge.
                    gauge_proof_data["active_campaigns_ids"] = [
                        composite_campaign_id
                    ]
                    gauge_proof_data["listed_users"] = {
                        composite_campaign_id: process_listed_users(
                            protocol,
                            gauge_address,
                            block_number,
                            listed_users,
                        )
                    }
                    gauge_proofs_cache[gauge_address] = gauge_proof_data
                    # For votes, keep only the raw vote details.
                    gauge_votes_cache[gauge_address] = {
                        "users": gauge_vote_data["users"]
                    }
                else:
                    gauge_proof_data = gauge_proofs_cache[gauge_address]
                    # Merge vote data if needed.
                    new_vote_data = (
                        await process_gauge(
                            protocol,
                            gauge_address,
                            current_epoch,
                            block_number,
                            user_proofs_cache,
                        )
                    )[1]["users"]
                    gauge_votes_cache[gauge_address]["users"].update(
                        new_vote_data
                    )
                    # Append the campaign id if not already present.
                    if composite_campaign_id not in gauge_proof_data.get(
                        "active_campaigns_ids", []
                    ):
                        gauge_proof_data.setdefault(
                            "active_campaigns_ids", []
                        ).append(composite_campaign_id)
                        gauge_proof_data.setdefault("listed_users", {})[
                            composite_campaign_id
                        ] = process_listed_users(
                            protocol,
                            gauge_address,
                            block_number,
                            listed_users,
                        )
                # Save gauge proof data for this platform.
                output_data["platforms"][chain_id][platform_address]["gauges"][
                    gauge_address
                ] = gauge_proof_data
                # Save gauge vote data (raw vote details) for this platform.
                output_data["votes"][chain_id][platform_address].setdefault(
                    "gauges", {}
                )[gauge_address] = gauge_votes_cache[gauge_address]

        console.print(
            f"Finished processing chain {chain_id} for protocol: [blue]{protocol}[/blue]"
        )
    return output_data


def write_protocol_data(
    protocol: str, current_epoch: int, processed_data: Dict[str, Any]
):
    """
    Write processed protocol data to files using the new folder structure.

    This writes:
      - The protocol header and index (proofs only) in header.json and index.json.
      - Individual gauge files under each platform/chain folder.
      - A separate votes.json file containing only vote data (raw vote details), along with epoch and block_data.
    """
    protocol_dir = os.path.join(TEMP_DIR, protocol.lower())
    os.makedirs(protocol_dir, exist_ok=True)

    # Build platforms index for proofs.
    platforms_by_address: Dict[str, Dict[str, Any]] = {}
    for chain_id, chain_platforms in processed_data["platforms"].items():
        for platform_addr, platform_data in chain_platforms.items():
            platforms_by_address.setdefault(platform_addr, {})[chain_id] = {
                "chain_id": chain_id,
                "platform_address": platform_addr,
                "block_data": processed_data["chains"]
                .get(chain_id, {})
                .get("block_data", {}),
                "gauges": platform_data.get("gauges", {}),
            }

    rep_platform_addr = next(iter(platforms_by_address))
    rep_chain_id = next(iter(platforms_by_address[rep_platform_addr]))
    rep_chain_header = processed_data["chains"].get(rep_chain_id, {})

    # Write protocol-level header.
    header_data = {
        "epoch": current_epoch,
        "block_data": rep_chain_header.get("block_data", {}),
        "gauge_controller_proof": rep_chain_header.get(
            "gauge_controller_proof", ""
        ),
    }
    with open(os.path.join(protocol_dir, "header.json"), "w") as f:
        json.dump(header_data, f)

    # Write main index file (proofs only).
    index_data = {
        "epoch": current_epoch,
        "block_data": rep_chain_header.get("block_data", {}),
        "gauge_controller_proof": rep_chain_header.get(
            "gauge_controller_proof", ""
        ),
        "platforms": platforms_by_address,
    }
    with open(os.path.join(protocol_dir, "index.json"), "w") as f:
        json.dump(index_data, f)

    # Write individual gauge files for each platform/chain (proofs only).
    for platform_addr, chains in platforms_by_address.items():
        platform_folder = os.path.join(protocol_dir, platform_addr.lower())
        os.makedirs(platform_folder, exist_ok=True)
        for chain_id, chain_info in chains.items():
            chain_folder = os.path.join(platform_folder, chain_id)
            os.makedirs(chain_folder, exist_ok=True)
            with open(os.path.join(chain_folder, "index.json"), "w") as f:
                json.dump(chain_info, f)
            for gauge_address, gauge_data in chain_info["gauges"].items():
                gauge_file = os.path.join(
                    chain_folder, f"{gauge_address.lower()}.json"
                )
                with open(gauge_file, "w") as f:
                    json.dump(gauge_data, f)
            console.print(
                f"Saved gauge files for platform [cyan]{platform_addr}[/cyan] on chain [blue]{chain_id}[/blue] in {chain_folder}"
            )

    # Build and write the votes file (only gauge vote details plus epoch and block_data).
    votes_platforms: Dict[str, Any] = {}
    votes_data = processed_data.get("votes", {})
    for chain_id, chain_platforms in votes_data.items():
        for platform_addr, platform_data in chain_platforms.items():
            votes_platforms.setdefault(platform_addr, {})[chain_id] = {
                "gauges": platform_data.get("gauges", {})
            }
    votes_index_data = {
        "epoch": current_epoch,
        "block_data": rep_chain_header.get("block_data", {}),
        "platforms": votes_platforms,
    }
    with open(os.path.join(protocol_dir, "votes.json"), "w") as f:
        json.dump(votes_index_data, f)


async def main(all_protocols_data: AllProtocolsData, current_epoch: int):
    # Clear cache to ensure fresh campaign data

    campaign_service.clear_cache()

    
    console.print(
        f"Starting active proofs generation for epoch: [yellow]{current_epoch}[/yellow]"
    )
    for protocol, protocol_data in all_protocols_data["protocols"].items():
        if not protocol_data["platforms"]:
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
