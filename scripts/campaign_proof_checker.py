#!/usr/bin/env python3
"""
Campaign Proof Checker - Get proofs to insert and updates needed for a specific campaign.

This script:
1. Fetches a specific campaign by ID
2. Checks all periods for proof insertion status
3. Generates the proofs that need to be inserted
4. Shows what updates need to be done

Usage:
    python scripts/campaign_proof_checker.py --campaign-id 657 --protocol curve
"""

import argparse
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from votemarket_toolkit.campaigns import CampaignService
from votemarket_toolkit.data import EligibilityService
from votemarket_toolkit.proofs import VoteMarketProofs
from votemarket_toolkit.shared import registry
from votemarket_toolkit.utils import get_rounded_epoch

console = Console()


async def find_campaign_by_id(
    campaign_service: CampaignService, protocol: str, campaign_id: int
) -> Optional[tuple]:
    """
    Find a campaign by ID across all platforms for a protocol.

    Returns: (campaign_data, chain_id, platform_address) or None
    """
    console.print(
        f"\n[cyan]Searching for campaign {campaign_id} on {protocol}...[/cyan]"
    )

    platforms = registry.get_all_platforms(protocol)

    for platform in platforms:
        chain_id = platform["chain_id"]
        platform_address = platform["address"]

        chain_name = {
            1: "Ethereum",
            10: "Optimism",
            137: "Polygon",
            8453: "Base",
            42161: "Arbitrum",
        }.get(chain_id, f"Chain {chain_id}")

        console.print(f"  Checking {chain_name}...")

        try:
            result = await campaign_service.get_campaigns(
                chain_id=chain_id,
                platform_address=platform_address,
                campaign_id=campaign_id,
                check_proofs=True,
            )

            if result.success and result.data:
                campaign = result.data[0]
                console.print(
                    f"  [green]✓ Found campaign {campaign_id} on {chain_name}![/green]"
                )
                return (campaign, chain_id, platform_address)
            elif result.success:
                # Campaign not found on this chain - continue searching
                console.print(f"  [dim]Campaign {campaign_id} not found on {chain_name}[/dim]")
            else:
                # Error occurred
                console.print(f"  [yellow]Warning: {result.errors[0].message[:100]}[/yellow]")

        except Exception as e:
            # Only show warnings for unexpected errors
            error_msg = str(e)
            if "Panic error 0x11" not in error_msg and "arithmetic overflow" not in error_msg.lower():
                # Check for data size errors - try fetching with direct contract call
                if "max code size" in error_msg.lower() or "Period count mismatch" in error_msg:
                    console.print(
                        f"  [yellow]Campaign {campaign_id} on {chain_name} has too many periods. "
                        f"Trying direct fetch...[/yellow]"
                    )
                    try:
                        # Try fetching without checking proofs and let it handle partial data
                        retry_result = await campaign_service.get_campaigns(
                            chain_id=chain_id,
                            platform_address=platform_address,
                            campaign_id=campaign_id,
                            check_proofs=False,  # Disable proof checking for large campaigns
                        )
                        if retry_result.success and retry_result.data:
                            campaign = retry_result.data[0]
                            console.print(
                                f"  [green]✓ Found campaign {campaign_id} on {chain_name} (partial data)![/green]"
                            )
                            return (campaign, chain_id, platform_address)
                    except Exception as retry_error:
                        console.print(
                            f"  [red]✗ Unable to fetch campaign {campaign_id} on {chain_name}: "
                            f"data too large[/red]"
                        )
                else:
                    console.print(f"  [yellow]Warning: {error_msg[:100]}[/yellow]")
            else:
                console.print(f"  [dim]Campaign {campaign_id} not found on {chain_name}[/dim]")
            continue

    return None


def display_campaign_info(campaign: Dict, chain_id: int, platform_address: str):
    """Display campaign information."""
    campaign_data = campaign["campaign"]

    table = Table(title="Campaign Information")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Campaign ID", str(campaign["id"]))
    table.add_row("Chain ID", str(chain_id))
    table.add_row("Platform", platform_address)
    table.add_row("Gauge", campaign_data["gauge"])
    table.add_row("Manager", campaign_data["manager"])
    table.add_row("Reward Token", campaign_data["reward_token"])

    # Format timestamps
    start_ts = campaign_data["start_timestamp"]
    end_ts = campaign_data["end_timestamp"]
    start_dt = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d")
    end_dt = datetime.fromtimestamp(end_ts).strftime("%Y-%m-%d")

    table.add_row("Start Date", f"{start_dt} (epoch: {start_ts})")
    table.add_row("End Date", f"{end_dt} (epoch: {end_ts})")
    # Display total periods
    actual_periods = len(campaign.get("periods", []))
    table.add_row("Total Periods", str(actual_periods))
    table.add_row("Remaining Periods", str(campaign.get("remaining_periods", 0)))
    table.add_row("Is Closed", str(campaign.get("is_closed", False)))

    console.print(table)


def analyze_periods_status(campaign: Dict) -> Dict[str, List]:
    """
    Analyze which periods need proofs or updates.

    Returns dict with:
    - needs_block: periods missing block header
    - needs_point_data: periods missing point data proof
    - complete: periods with all proofs inserted
    """
    periods = campaign.get("periods", [])

    needs_block = []
    needs_point_data = []
    complete = []

    for period in periods:
        epoch = period["timestamp"]
        block_updated = period.get("block_updated", False)
        point_inserted = period.get("point_data_inserted", False)

        status = {
            "epoch": epoch,
            "epoch_date": datetime.fromtimestamp(epoch).strftime("%Y-%m-%d"),
            "amount": period.get("amount", 0),
            "block_updated": block_updated,
            "point_data_inserted": point_inserted,
            "block_number": period.get("block_number"),
            "block_hash": period.get("block_hash"),
        }

        if not block_updated:
            needs_block.append(status)
        elif not point_inserted:
            needs_point_data.append(status)
        else:
            complete.append(status)

    return {
        "needs_block": needs_block,
        "needs_point_data": needs_point_data,
        "complete": complete,
    }


def display_periods_analysis(analysis: Dict):
    """Display analysis of period status."""
    console.print("\n[bold]Period Status Analysis:[/bold]")

    # Complete periods
    complete = analysis["complete"]
    if complete:
        console.print(
            f"\n[green]✓ {len(complete)} periods are complete (all proofs inserted)[/green]"
        )

    # Needs block
    needs_block = analysis["needs_block"]
    if needs_block:
        console.print(
            f"\n[yellow]⚠ {len(needs_block)} periods need block header inserted:[/yellow]"
        )
        table = Table()
        table.add_column("Epoch", style="cyan")
        table.add_column("Date", style="white")
        table.add_column("Amount", style="green")

        for period in needs_block[:10]:  # Show first 10
            table.add_row(
                str(period["epoch"]),
                period["epoch_date"],
                str(period["amount"]),
            )

        if len(needs_block) > 10:
            table.add_row("...", "...", "...")

        console.print(table)

    # Needs point data
    needs_point_data = analysis["needs_point_data"]
    if needs_point_data:
        console.print(
            f"\n[yellow]⚠ {len(needs_point_data)} periods need point data proof:[/yellow]"
        )
        table = Table()
        table.add_column("Epoch", style="cyan")
        table.add_column("Date", style="white")
        table.add_column("Block Number", style="blue")
        table.add_column("Amount", style="green")

        for period in needs_point_data[:10]:  # Show first 10
            table.add_row(
                str(period["epoch"]),
                period["epoch_date"],
                str(period.get("block_number", "N/A")),
                str(period["amount"]),
            )

        if len(needs_point_data) > 10:
            table.add_row("...", "...", "...", "...")

        console.print(table)


async def generate_proofs_for_period(
    vm_proofs: VoteMarketProofs,
    vm_eligibility: EligibilityService,
    protocol: str,
    gauge: str,
    epoch: int,
    block_number: int,
) -> Dict:
    """Generate all proofs needed for a specific period."""
    console.print(f"\n[cyan]Generating proofs for epoch {epoch}...[/cyan]")

    # Generate gauge proof (includes point data proof)
    console.print("  Generating gauge proof...")
    gauge_result = vm_proofs.get_gauge_proof(
        protocol=protocol,
        gauge_address=gauge,
        current_epoch=epoch,
        block_number=block_number,
    )
    if not gauge_result.success:
        console.print(f"  [red]✗ Failed to generate gauge proof: {gauge_result.errors[0].message}[/red]")
        return None
    gauge_proof = gauge_result.data
    console.print("  [green]✓ Gauge proof generated[/green]")

    # Get eligible users
    console.print("  Finding eligible users...")
    eligible_result = await vm_eligibility.get_eligible_users(
        protocol, gauge, epoch, block_number
    )
    if eligible_result.success:
        eligible_users = eligible_result.data
        console.print(f"  [green]✓ Found {len(eligible_users)} eligible users[/green]")
    else:
        console.print(f"  [red]✗ Failed to get eligible users: {eligible_result.errors[0].message}[/red]")
        eligible_users = []

    # Generate user proofs
    user_proofs = {}
    if eligible_users:
        console.print(f"  Generating proofs for {len(eligible_users)} users...")

        for i, user in enumerate(eligible_users[:10], 1):  # Limit to first 10 for speed
            user_address = user["user"]
            user_result = vm_proofs.get_user_proof(
                protocol=protocol,
                gauge_address=gauge,
                user=user_address,
                block_number=block_number,
            )
            if user_result.success:
                user_proof = user_result.data
                user_proofs[user_address] = {
                    "storage_proof": "0x" + user_proof["storage_proof"].hex(),
                    "account_proof": "0x" + user_proof["account_proof"].hex(),
                    "vote_data": {
                        "last_vote": user["last_vote"],
                        "slope": user["slope"],
                        "power": user["power"],
                        "end": user["end"],
                    },
                }
                console.print(f"    [{i}/{min(len(eligible_users), 10)}] {user_address[:10]}...")
            else:
                console.print(f"    [red]✗ Failed for {user_address}: {user_result.errors[0].message[:50]}[/red]")

        if len(eligible_users) > 10:
            console.print(f"    [yellow]... and {len(eligible_users) - 10} more users[/yellow]")

    return {
        "epoch": epoch,
        "block_number": block_number,
        "gauge_controller_proof": "0x" + gauge_proof["gauge_controller_proof"].hex(),
        "point_data_proof": "0x" + gauge_proof["point_data_proof"].hex(),
        "eligible_users_count": len(eligible_users),
        "user_proofs_generated": len(user_proofs),
        "user_proofs": user_proofs,
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Check proof status and generate proofs for a campaign"
    )
    parser.add_argument(
        "--campaign-id",
        type=int,
        required=True,
        help="Campaign ID to check",
    )
    parser.add_argument(
        "--protocol",
        type=str,
        default="curve",
        help="Protocol name (curve, balancer, etc.)",
    )
    parser.add_argument(
        "--generate-proofs",
        action="store_true",
        help="Generate proofs for periods that need them (first 3 periods only)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path for generated proofs (JSON)",
    )

    args = parser.parse_args()

    console.print(
        Panel.fit(
            f"[bold cyan]Campaign Proof Checker[/bold cyan]\n"
            f"Campaign ID: {args.campaign_id}\n"
            f"Protocol: {args.protocol}",
            border_style="cyan",
        )
    )

    # Initialize services
    campaign_service = CampaignService()

    # Find campaign
    result = await find_campaign_by_id(
        campaign_service, args.protocol, args.campaign_id
    )

    if not result:
        console.print(
            f"\n[red]✗ Campaign {args.campaign_id} not found on {args.protocol}[/red]"
        )
        return

    campaign, chain_id, platform_address = result

    # Display campaign info
    console.print("\n")
    display_campaign_info(campaign, chain_id, platform_address)

    # Analyze periods
    analysis = analyze_periods_status(campaign)
    display_periods_analysis(analysis)

    # Generate proofs if requested
    if args.generate_proofs:
        console.print("\n[bold cyan]Generating Proofs...[/bold cyan]")

        vm_proofs = VoteMarketProofs(chain_id=1)  # Curve is on mainnet
        vm_eligibility = EligibilityService(chain_id=1)

        gauge = campaign["campaign"]["gauge"]
        protocol = args.protocol

        generated_proofs = []

        # Generate for periods that need point data (have block, missing point data)
        periods_to_process = analysis["needs_point_data"][:3]  # First 3 only

        if not periods_to_process:
            console.print(
                "\n[green]✓ No periods need proofs! All periods are complete.[/green]"
            )
        else:
            for period in periods_to_process:
                epoch = period["epoch"]
                block_number = period.get("block_number")

                if not block_number:
                    console.print(
                        f"\n[yellow]⚠ Skipping epoch {epoch} - no block number set[/yellow]"
                    )
                    continue

                proof_data = await generate_proofs_for_period(
                    vm_proofs,
                    vm_eligibility,
                    protocol,
                    gauge,
                    epoch,
                    block_number,
                )

                if proof_data:
                    generated_proofs.append(proof_data)

            # Save proofs if output specified
            if args.output and generated_proofs:
                output_data = {
                    "campaign_id": args.campaign_id,
                    "protocol": protocol,
                    "chain_id": chain_id,
                    "platform_address": platform_address,
                    "gauge": gauge,
                    "proofs": generated_proofs,
                }

                with open(args.output, "w") as f:
                    json.dump(output_data, f, indent=2)

                console.print(
                    f"\n[green]✓ Proofs saved to {args.output}[/green]"
                )

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Complete periods: {len(analysis['complete'])}")
    console.print(f"  Need block header: {len(analysis['needs_block'])}")
    console.print(f"  Need point data: {len(analysis['needs_point_data'])}")
    console.print("\n[green]✓ Analysis complete![/green]")


if __name__ == "__main__":
    asyncio.run(main())
