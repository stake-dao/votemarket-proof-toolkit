import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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

# Retry configuration for gauge validation - more aggressive for completeness
VALIDATION_MAX_RETRIES = 5
VALIDATION_BASE_DELAY = 3.0  # seconds

# Bulk eth_getProof mode (opt-in): group the storage keys of many users and
# gauges into a few eth_getProof calls instead of one call per proof.
# Enable with --bulk-proofs or VM_BULK_PROOFS=1; tune with --keys-per-call
# or VM_BULK_KEYS_PER_CALL. The generated proofs are byte-identical.
BULK_PROOFS = os.getenv("VM_BULK_PROOFS", "0") == "1"


def _parse_positive_int_env(name: str, default: int) -> int:
    """Parse a positive integer env var, falling back to the default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        console.print(
            f"[yellow]Invalid {name}={raw!r}; using default {default}[/yellow]"
        )
        return default
    if value < 1:
        console.print(
            f"[yellow]{name} must be >= 1; using default {default}[/yellow]"
        )
        return default
    return value


BULK_KEYS_PER_CALL = _parse_positive_int_env("VM_BULK_KEYS_PER_CALL", 100)

# Track processing results for summary
processing_stats: Dict[str, Dict[str, Any]] = {
    "processed_gauges": [],
    "skipped_invalid_gauges": [],
    "failed_validation_gauges": [],  # RPC/network failures - these are problems
    "failed_user_proofs": [],  # Individual user proofs that failed (bulk mode)
}


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


# ---------------------------------------------------------------------------
# Bulk eth_getProof path (opt-in, see BULK_PROOFS)
# ---------------------------------------------------------------------------


async def _get_eligible_users_with_retry(
    protocol: str,
    gauge_address: str,
    current_epoch: int,
    block_number: int,
    max_retries: int,
) -> List[Dict[str, Any]]:
    """Eligibility lookup with the same retry policy as process_gauge."""
    for attempt in range(max_retries):
        result = await vm_eligibility.get_eligible_users(
            protocol, gauge_address, current_epoch, block_number
        )
        if result.success:
            return result.data or []
        delay = 2.0 * (2**attempt)
        console.print(
            f"[yellow]Eligibility check attempt {attempt + 1}/{max_retries} failed. Retrying in {delay}s...[/yellow]"
        )
        time.sleep(delay)
    return []


def _bulk_proofs(
    protocol: str,
    gauge_address: str,
    block_number: int,
    users: List[str],
    gauge_epoch: Optional[int] = None,
    max_retries: int = 3,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, str], List[str]]:
    """
    One grouped eth_getProof pass for a gauge.

    Returns (gauge_proof or None, {user: storage_proof_hex}, failed_users).
    Raises when nothing at all could be generated.
    """
    gauge_epochs = (
        [(gauge_address, gauge_epoch)] if gauge_epoch is not None else []
    )
    result = vm_proofs.get_proofs_bulk(
        protocol=protocol,
        block_number=block_number,
        gauge_epochs=gauge_epochs,
        users=[(gauge_address, user) for user in users],
        keys_per_call=BULK_KEYS_PER_CALL,
        max_retries=max_retries,
    )
    if not result.success:
        error_msg = (
            result.errors[0].message if result.errors else "Unknown error"
        )
        raise Exception(
            f"Bulk proof generation failed for gauge {gauge_address}: {error_msg}"
        )

    data = result.data
    stats = data.stats
    console.print(
        f"[dim]Bulk eth_getProof: {stats.rpc_calls} call(s) for {stats.keys} keys / "
        f"{stats.requests} proofs ({stats.splits} splits, {stats.failed_requests} failed)[/dim]"
    )

    gauge_proof = None
    if gauge_epoch is not None:
        gauge_proof = data.gauge_proofs.get(
            (gauge_address.lower(), get_rounded_epoch(gauge_epoch))
        )

    user_proofs: Dict[str, str] = {}
    failed_users: List[str] = []
    for user in users:
        proof = data.user_proofs.get((gauge_address.lower(), user.lower()))
        if proof is None:
            failed_users.append(user.lower())
        else:
            user_proofs[user.lower()] = "0x" + proof["storage_proof"].hex()
    return gauge_proof, user_proofs, failed_users


async def _process_gauge_bulk(
    protocol: str,
    gauge_address: str,
    current_epoch: int,
    block_number: int,
    user_proofs_cache: Dict[str, Any],
    max_retries: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Bulk variant of process_gauge: same outputs, grouped eth_getProof."""
    console.print(
        f"Querying votes for gauge: [magenta]{gauge_address}[/magenta]"
    )
    gauge_votes = await votes_service.get_gauge_votes(
        protocol, gauge_address, block_number
    )
    console.print(
        f"Found [yellow]{len(gauge_votes.votes)}[/yellow] votes for gauge: [magenta]{gauge_address}[/magenta]"
    )

    console.print(
        f"Querying eligible users for gauge: [magenta]{gauge_address}[/magenta]"
    )
    eligible_users = await _get_eligible_users_with_retry(
        protocol, gauge_address, current_epoch, block_number, max_retries
    )
    console.print(
        f"Found [yellow]{len(eligible_users)}[/yellow] eligible users for gauge: [magenta]{gauge_address}[/magenta]"
    )

    users_to_generate = list(
        dict.fromkeys(
            user["user"].lower()
            for user in eligible_users
            if f"{gauge_address}:{user['user'].lower()}"
            not in user_proofs_cache
        )
    )
    console.print(
        f"Generating point data proof + {len(users_to_generate)} user proof(s) in bulk"
    )
    gauge_proof, new_user_proofs, failed_users = _bulk_proofs(
        protocol,
        gauge_address,
        block_number,
        users_to_generate,
        gauge_epoch=current_epoch,
        max_retries=max_retries,
    )
    if gauge_proof is None:
        raise Exception(
            f"Failed to generate gauge proof for {gauge_address} (bulk mode)"
        )

    gauge_proof_data = {
        "point_data_proof": "0x" + gauge_proof["point_data_proof"].hex(),
        "users": {},
    }
    gauge_vote_data = {"users": {}}

    for user in eligible_users:
        user_address = user["user"].lower()
        cache_key = f"{gauge_address}:{user_address}"
        if cache_key not in user_proofs_cache:
            if user_address not in new_user_proofs:
                continue  # Failed user: skipped, like the per-request path
            user_proofs_cache[cache_key] = {
                "storage_proof": new_user_proofs[user_address],
                "last_vote": user["last_vote"],
                "slope": user["slope"],
                "power": user["power"],
                "end": user["end"],
            }
        proof_info = user_proofs_cache[cache_key]
        gauge_proof_data["users"][user_address] = {
            "storage_proof": proof_info["storage_proof"]
        }
        gauge_vote_data["users"][user_address] = {
            "last_vote": proof_info["last_vote"],
            "slope": proof_info["slope"],
            "power": proof_info["power"],
            "end": proof_info["end"],
        }

    if failed_users:
        console.print(
            f"[yellow]Warning: {len(failed_users)} user(s) failed for gauge {gauge_address}[/yellow]"
        )
        for user in failed_users:
            processing_stats["failed_user_proofs"].append(
                {
                    "protocol": protocol,
                    "gauge": gauge_address,
                    "user": user,
                    "kind": "eligible",
                }
            )

    return gauge_proof_data, gauge_vote_data


def _record_failed_listed_users(
    protocol: str, gauge_address: str, users: List[str]
) -> None:
    for user in users:
        processing_stats["failed_user_proofs"].append(
            {
                "protocol": protocol,
                "gauge": gauge_address,
                "user": user,
                "kind": "listed",
            }
        )


def _process_listed_users_bulk(
    protocol: str,
    gauge_address: str,
    block_number: int,
    listed_users: List[str],
    max_retries: int = 5,
) -> Dict[str, Any]:
    """Bulk variant of process_listed_users (never raises, skips failures)."""
    users = list(dict.fromkeys(user.lower() for user in listed_users))
    if not users:
        return {}
    try:
        _, user_proofs, failed_users = _bulk_proofs(
            protocol,
            gauge_address,
            block_number,
            users,
            max_retries=max_retries,
        )
    except Exception as exc:
        console.print(
            f"[red]Failed to generate listed user proofs for gauge {gauge_address}: {exc}[/red]"
        )
        _record_failed_listed_users(protocol, gauge_address, users)
        return {}
    for user in failed_users:
        console.print(
            f"[red]Failed to generate proof for listed user {user}. Skipping.[/red]"
        )
    _record_failed_listed_users(protocol, gauge_address, failed_users)
    return {
        user: {"storage_proof": proof} for user, proof in user_proofs.items()
    }


async def process_gauge(
    protocol: str,
    gauge_address: str,
    current_epoch: int,
    block_number: int,
    user_proofs_cache: Dict[str, Any],
    max_retries: int = 5,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a gauge by generating its proof and gathering vote details.

    Resilient version: retries on failure, continues processing users even if some fail.

    Returns:
      - gauge_proof_data: containing proofs (e.g. point_data_proof and storage proofs for each user).
      - gauge_vote_data: containing only the raw vote details for each eligible user.
    """
    if BULK_PROOFS:
        return await _process_gauge_bulk(
            protocol,
            gauge_address,
            current_epoch,
            block_number,
            user_proofs_cache,
            max_retries,
        )

    console.print(
        f"Querying votes for gauge: [magenta]{gauge_address}[/magenta]"
    )
    gauge_votes = await votes_service.get_gauge_votes(
        protocol, gauge_address, block_number
    )
    console.print(
        f"Found [yellow]{len(gauge_votes.votes)}[/yellow] votes for gauge: [magenta]{gauge_address}[/magenta]"
    )

    # Retry gauge proof generation with longer delays
    console.print("Generating point data proof")
    gauge_proofs_result = None
    for attempt in range(max_retries):
        gauge_proofs_result = vm_proofs.get_gauge_proof(
            protocol=protocol,
            gauge_address=gauge_address,
            current_epoch=current_epoch,
            block_number=block_number,
            max_retries=3,  # Internal retries per attempt
        )
        if gauge_proofs_result.success:
            break
        delay = 2.0 * (2 ** attempt)  # Exponential backoff: 2, 4, 8, 16, 32 seconds
        console.print(
            f"[yellow]Gauge proof attempt {attempt + 1}/{max_retries} failed. Retrying in {delay}s...[/yellow]"
        )
        time.sleep(delay)

    if not gauge_proofs_result.success:
        error_msg = gauge_proofs_result.errors[0].message if gauge_proofs_result.errors else "Unknown error"
        raise Exception(f"Failed to generate gauge proof after {max_retries} attempts: {error_msg}")

    gauge_proofs = gauge_proofs_result.data
    gauge_proof_data = {
        "point_data_proof": "0x" + gauge_proofs["point_data_proof"].hex(),
        "users": {},
    }
    gauge_vote_data = {"users": {}}

    console.print(
        f"Querying eligible users for gauge: [magenta]{gauge_address}[/magenta]"
    )

    # Retry eligibility check
    eligible_users = []
    for attempt in range(max_retries):
        eligible_users_result = await vm_eligibility.get_eligible_users(
            protocol, gauge_address, current_epoch, block_number
        )
        if eligible_users_result.success:
            eligible_users = eligible_users_result.data or []
            break
        delay = 2.0 * (2 ** attempt)
        console.print(
            f"[yellow]Eligibility check attempt {attempt + 1}/{max_retries} failed. Retrying in {delay}s...[/yellow]"
        )
        time.sleep(delay)

    console.print(
        f"Found [yellow]{len(eligible_users)}[/yellow] eligible users for gauge: [magenta]{gauge_address}[/magenta]"
    )

    failed_users = []
    for user in eligible_users:
        user_address = user["user"].lower()
        cache_key = f"{gauge_address}:{user_address}"
        if cache_key not in user_proofs_cache:
            console.print(
                f"Generating proof for user: [cyan]{user_address}[/cyan]"
            )
            # Retry user proof with resilience - don't let one user fail the whole gauge
            user_proofs_result = None
            for attempt in range(max_retries):
                user_proofs_result = vm_proofs.get_user_proof(
                    protocol=protocol,
                    gauge_address=gauge_address,
                    user=user_address,
                    block_number=block_number,
                    max_retries=3,
                )
                if user_proofs_result.success:
                    break
                delay = 1.0 * (2 ** attempt)  # 1, 2, 4, 8, 16 seconds
                if attempt < max_retries - 1:
                    console.print(
                        f"[yellow]User proof attempt {attempt + 1}/{max_retries} for {user_address[:10]}... failed. Retrying in {delay}s...[/yellow]"
                    )
                    time.sleep(delay)

            if not user_proofs_result.success:
                console.print(
                    f"[red]Failed to generate proof for user {user_address} after {max_retries} attempts. Skipping user.[/red]"
                )
                failed_users.append(user_address)
                continue  # Skip this user but continue with others

            user_proofs = user_proofs_result.data
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

    if failed_users:
        console.print(
            f"[yellow]Warning: {len(failed_users)} user(s) failed for gauge {gauge_address}[/yellow]"
        )

    return gauge_proof_data, gauge_vote_data


def process_listed_users(
    protocol: str,
    gauge_address: str,
    block_number: int,
    listed_users: List[str],
    max_retries: int = 5,
) -> Dict[str, Any]:
    """
    Process the listed users for a campaign by generating a storage proof.
    (Listed users do not include raw vote details.)

    Resilient version: retries on failure, skips individual users if they consistently fail.
    """
    if BULK_PROOFS:
        return _process_listed_users_bulk(
            protocol, gauge_address, block_number, listed_users, max_retries
        )

    listed_users_data = {}
    for listed_user in listed_users:
        console.print(
            f"Generating proof for listed user: [cyan]{listed_user}[/cyan]"
        )
        user_proofs_result = None
        for attempt in range(max_retries):
            user_proofs_result = vm_proofs.get_user_proof(
                protocol=protocol,
                gauge_address=gauge_address,
                user=listed_user,
                block_number=block_number,
                max_retries=3,
            )
            if user_proofs_result.success:
                break
            delay = 1.0 * (2 ** attempt)
            if attempt < max_retries - 1:
                console.print(
                    f"[yellow]Listed user proof attempt {attempt + 1}/{max_retries} for {listed_user[:10]}... failed. Retrying in {delay}s...[/yellow]"
                )
                time.sleep(delay)

        if not user_proofs_result.success:
            console.print(
                f"[red]Failed to generate proof for listed user {listed_user} after {max_retries} attempts. Skipping.[/red]"
            )
            continue  # Skip this user but continue with others

        user_proofs = user_proofs_result.data
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
            # Retry gauge controller proof with resilience
            gauge_controller_result = None
            for attempt in range(5):
                gauge_controller_result = vm_proofs.get_gauge_proof(
                    protocol=protocol,
                    gauge_address="0x0000000000000000000000000000000000000000",
                    current_epoch=current_epoch,
                    block_number=block_number,
                    max_retries=3,
                )
                if gauge_controller_result.success:
                    break
                delay = 2.0 * (2 ** attempt)
                console.print(
                    f"[yellow]Gauge controller proof attempt {attempt + 1}/5 failed. Retrying in {delay}s...[/yellow]"
                )
                time.sleep(delay)

            if not gauge_controller_result.success:
                error_msg = gauge_controller_result.errors[0].message if gauge_controller_result.errors else "Unknown"
                console.print(f"[red]Failed to generate gauge controller proof for chain {chain_id}: {error_msg}[/red]")
                continue  # Skip this chain but continue with others

            gauge_controller = gauge_controller_result.data
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
                # Retry campaign fetch with resilience
                campaigns_result = None
                all_campaigns = []
                for attempt in range(5):
                    campaigns_result = await campaign_svc.get_campaigns(
                        chain_id, platform_address
                    )
                    if campaigns_result.success:
                        all_campaigns = campaigns_result.data or []
                        break
                    delay = 2.0 * (2 ** attempt)
                    console.print(
                        f"[yellow]Campaign fetch attempt {attempt + 1}/5 failed for {platform_address}. Retrying in {delay}s...[/yellow]"
                    )
                    time.sleep(delay)

                if not campaigns_result.success:
                    error_msg = campaigns_result.errors[0].message if campaigns_result.errors else "Unknown"
                    console.print(f"[red]Failed to fetch campaigns for platform {platform_address}: {error_msg}. Skipping platform.[/red]")
                    continue  # Skip this platform but continue with others

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

                # Validate gauge with script-level retry on RPC failures
                validation = None
                last_error = None
                for attempt in range(VALIDATION_MAX_RETRIES):
                    validation = vm_proofs.is_valid_gauge(protocol, gauge_address)
                    if validation.success:
                        break
                    # RPC failure - retry with exponential backoff
                    last_error = validation.errors[0].message if validation.errors else "Unknown error"
                    if attempt < VALIDATION_MAX_RETRIES - 1:
                        delay = VALIDATION_BASE_DELAY * (2 ** attempt)
                        console.print(
                            f"[yellow]Validation attempt {attempt + 1}/{VALIDATION_MAX_RETRIES} failed for gauge "
                            f"[magenta]{gauge_address}[/magenta]: {last_error}. Retrying in {delay}s...[/yellow]"
                        )
                        time.sleep(delay)

                # Handle validation failures explicitly - never skip silently
                if not validation.success:
                    # All retries exhausted - validation call failed
                    console.print(
                        f"[bold red]VALIDATION FAILED[/bold red] (after {VALIDATION_MAX_RETRIES} attempts) "
                        f"for gauge [magenta]{gauge_address}[/magenta]: {last_error}"
                    )
                    processing_stats["failed_validation_gauges"].append({
                        "gauge": gauge_address,
                        "protocol": protocol,
                        "platform": platform_address,
                        "campaign_id": campaign["id"],
                        "error": last_error,
                    })
                    continue

                if not validation.data.is_valid:
                    # Gauge is legitimately invalid (not in gauge controller)
                    console.print(
                        f"[yellow]Skipping invalid gauge[/yellow] [magenta]{gauge_address}[/magenta]: {validation.data.reason}"
                    )
                    processing_stats["skipped_invalid_gauges"].append({
                        "gauge": gauge_address,
                        "protocol": protocol,
                        "platform": platform_address,
                        "campaign_id": campaign["id"],
                        "reason": validation.data.reason,
                    })
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
                    # Track successful processing
                    processing_stats["processed_gauges"].append({
                        "gauge": gauge_address,
                        "protocol": protocol,
                        "platform": platform_address,
                        "users_count": len(gauge_vote_data["users"]),
                    })
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


def print_processing_summary() -> str:
    """
    Print a summary of processing results.

    Returns:
        "all_failed"     if there were failures and NO gauges succeeded (total failure).
        "partial_failed" if there were failures but at least one gauge succeeded (partial success).
        "success"        if there were no failures.
    """
    console.print("\n" + "=" * 70)
    console.print("[bold]PROCESSING SUMMARY[/bold]")
    console.print("=" * 70)

    processed = processing_stats["processed_gauges"]
    skipped = processing_stats["skipped_invalid_gauges"]
    failed = processing_stats["failed_validation_gauges"]
    failed_users = processing_stats.get("failed_user_proofs", [])

    console.print(
        f"\n[bold]Results: {len(processed)} succeeded, {len(failed)} failed, {len(skipped)} skipped (invalid)[/bold]"
    )

    console.print(f"\n[green]✓ Processed gauges:[/green] {len(processed)}")
    for g in processed:
        console.print(f"  - {g['gauge']} ({g['protocol']}, {g['users_count']} users)")

    if skipped:
        console.print(f"\n[yellow]⊘ Skipped invalid gauges:[/yellow] {len(skipped)}")
        for g in skipped:
            console.print(f"  - {g['gauge']} ({g['protocol']}): {g['reason']}")

    if failed:
        console.print(f"\n[bold red]✗ VALIDATION FAILURES:[/bold red] {len(failed)}")
        console.print("[red]These gauges could not be validated due to RPC/network errors![/red]")
        for g in failed:
            console.print(f"  - {g['gauge']} ({g['protocol']}, campaign {g['campaign_id']})")
            console.print(f"    Error: {g['error']}")

    if failed_users:
        console.print(
            f"\n[yellow]⚠ Failed user proofs:[/yellow] {len(failed_users)}"
        )
        for item in failed_users:
            console.print(
                f"  - {item['user']} on {item['gauge']} "
                f"({item['protocol']}, {item['kind']})"
            )

    console.print("\n" + "=" * 70)

    if not failed and not failed_users:
        return "success"

    if not failed and failed_users:
        # Gauges are fine but some user proofs are missing: partial output
        console.print(
            f"[bold yellow]WARNING: {len(failed_users)} user proof(s) "
            "failed. Committing successful proofs.[/bold yellow]"
        )
        return "partial_failed"

    if processed:
        # Some gauges succeeded — partial success, commit what we have
        console.print(
            f"[bold yellow]WARNING: {len(failed)} gauge(s) failed validation, "
            f"but {len(processed)} gauge(s) succeeded.[/bold yellow]"
        )
        console.print(
            "[yellow]Committing successful proofs. Failed gauges will need to be retried.[/yellow]"
        )
        return "partial_failed"

    # No gauges succeeded at all — total failure
    console.print(
        f"[bold red]ERROR: {len(failed)} gauge(s) failed validation and no gauges succeeded![/bold red]"
    )
    console.print(
        "[red]Proof generation produced no usable output. Review failures above.[/red]"
    )
    return "all_failed"


async def main(all_protocols_data: AllProtocolsData, current_epoch: int) -> str:
    """
    Main entry point for active proofs generation.

    Returns:
        "all_failed"     if there were failures and NO gauges succeeded (total failure).
        "partial_failed" if there were failures but at least one gauge succeeded (partial success).
        "success"        if there were no failures.
    """
    # Reset stats for this run
    processing_stats["processed_gauges"] = []
    processing_stats["skipped_invalid_gauges"] = []
    processing_stats["failed_validation_gauges"] = []
    processing_stats["failed_user_proofs"] = []

    # Clear cache to ensure fresh campaign data
    campaign_service.clear_cache()

    console.print(
        f"Starting active proofs generation for epoch: [yellow]{current_epoch}[/yellow]"
    )
    console.print(
        "Proof generation mode: "
        + (
            f"[green]bulk[/green] ({BULK_KEYS_PER_CALL} keys per eth_getProof)"
            if BULK_PROOFS
            else "[cyan]per-request[/cyan]"
        )
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

    # Print summary and return outcome
    return print_processing_summary()


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
    parser.add_argument(
        "--bulk-proofs",
        action="store_true",
        help="Group storage keys into few eth_getProof calls (opt-in, same as VM_BULK_PROOFS=1)",
    )
    parser.add_argument(
        "--keys-per-call",
        type=int,
        default=None,
        help="Max storage keys per eth_getProof call in bulk mode (default: VM_BULK_KEYS_PER_CALL or 100)",
    )
    args = parser.parse_args()

    if args.bulk_proofs:
        BULK_PROOFS = True
    if args.keys_per_call is not None:
        if args.keys_per_call < 1:
            parser.error("--keys-per-call must be >= 1")
        BULK_KEYS_PER_CALL = args.keys_per_call

    with open(args.all_platforms_file, "r") as f:
        all_protocols_data = json.load(f)

    outcome = asyncio.run(main(all_protocols_data, args.current_epoch))

    if outcome == "all_failed":
        console.print(
            "[bold red]Active proofs generation completed with ERRORS — no successful proofs to commit[/bold red]"
        )
        sys.exit(1)
    elif outcome == "partial_failed":
        console.print(
            "[bold yellow]Active proofs generation completed with partial failures — committing successful proofs[/bold yellow]"
        )
        # Exit 0 so the CI/CD pipeline commits the successful proofs
    else:
        console.print(
            "[bold green]Active proofs generation completed successfully[/bold green]"
        )
