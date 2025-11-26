"""
User Campaign Status Command - Check proof insertion status for a specific user and campaign

This command allows users to verify if their proofs have been properly inserted
on the oracle for a specific VoteMarket campaign, enabling them to claim rewards.
"""

import argparse
import asyncio
import json
import sys
import time
from typing import Any, Dict, List, Optional

from eth_utils.address import to_checksum_address
from rich import print as rprint
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from votemarket_toolkit.campaigns.service import campaign_service
from votemarket_toolkit.shared import registry
from votemarket_toolkit.utils.formatters import (
    console,
    format_address,
    format_timestamp,
)
from votemarket_toolkit.utils.interactive import (
    select_campaign,
    select_chain,
    select_platform,
)

MAX_UINT256 = (2**256) - 1


def _create_period_status_table(
    periods: List[Dict], show_header: bool = True
) -> Table:
    """Create a Rich table for period status display."""
    table = Table(
        title="User Proof Status by Period" if show_header else None,
        show_header=True,
        header_style="bold",
    )
    table.add_column("Period", style="cyan", width=8)
    table.add_column("Epoch", style="yellow", width=11)
    table.add_column("Date", style="white", width=16)
    table.add_column("Block", style="yellow", width=10)
    table.add_column("Point Data", style="green", width=12)
    table.add_column("User Slope", style="blue", width=12)
    table.add_column("Slope Value", style="white", width=15)
    table.add_column("Last Vote", style="white", width=16)
    table.add_column("Claimable", style="magenta", width=10)

    # Add data rows
    for idx, period_status in enumerate(periods):
        period_num = f"#{idx + 1}"
        epoch_timestamp = str(period_status["timestamp"])
        date = format_timestamp(period_status["timestamp"])

        # Status indicators
        block_status = "✓" if period_status.get("block_updated") else "✗"
        point_status = "✓" if period_status.get("point_data_inserted") else "✗"
        user_slope_status = (
            "✓" if period_status.get("user_slope_inserted") else "✗"
        )

        # Slope details
        slope_value = "N/A"
        last_vote = "N/A"
        if period_status.get("user_slope_data"):
            slope_data = period_status["user_slope_data"]
            if slope_data.get("slope", 0) > 0:
                slope_value = f"{slope_data['slope']:,.0f}"
            if slope_data.get("last_vote"):
                last_vote = format_timestamp(slope_data["last_vote"])

        # Overall claimability
        claimable = "Yes" if period_status.get("is_claimable") else "No"
        claimable_style = "green" if claimable == "Yes" else "red"

        table.add_row(
            period_num,
            epoch_timestamp,
            date,
            block_status,
            point_status,
            user_slope_status,
            slope_value,
            last_vote,
            f"[{claimable_style}]{claimable}[/{claimable_style}]",
        )

    return table


def _resolve_platform_metadata(
    chain_id: Optional[int], platform_address: str
) -> Optional[Dict[str, Any]]:
    """Find protocol/version metadata for a platform address."""
    if chain_id is None:
        return None

    candidates = registry.get_platforms_for_chain(chain_id)
    platform_lower = platform_address.lower()
    for entry in candidates:
        if entry.get("address", "").lower() == platform_lower:
            return entry
    return None


async def list_user_voted_campaigns(
    chain_id: int,
    platform_address: str,
    user_address: str,
    protocol: Optional[str],
) -> List[Dict[str, Any]]:
    """
    List campaigns where the user currently has a recorded vote.

    Returns campaign summaries enriched with current vote slope information.
    """
    if not protocol:
        rprint(
            "[yellow]Unable to determine platform protocol. Listing skipped.[/yellow]"
        )
        return []

    if protocol.lower() == "pendle":
        rprint(
            "[yellow]Listing voted campaigns is not yet supported for Pendle platforms.[/yellow]"
        )
        return []

    rprint(
        Panel(
            f"Scanning campaigns for user votes: {format_address(user_address)}",
            style="bold cyan",
        )
    )

    campaigns = await campaign_service.get_campaigns(
        chain_id=chain_id,
        platform_address=platform_address,
        campaign_id=None,
        check_proofs=False,
    )

    if not campaigns:
        rprint("[yellow]No campaigns found on this platform.[/yellow]")
        return []

    gauge_controller_address = registry.get_gauge_controller(protocol)
    if not gauge_controller_address:
        rprint(
            f"[yellow]No gauge controller registered for protocol '{protocol}'.[/yellow]"
        )
        return []

    web3_service = campaign_service.get_web3_service(chain_id)
    # Use protocol-specific ABI for gauge controller
    abi_name = (
        "yb_gauge_controller"
        if protocol.lower() == "yb"
        else "gauge_controller"
    )
    gauge_controller = web3_service.get_contract(
        to_checksum_address(gauge_controller_address.lower()),
        abi_name,
    )

    loop = asyncio.get_running_loop()
    now = int(time.time())
    is_yb = protocol.lower() == "yb"

    async def fetch_vote_data(
        campaign: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        gauge_address = campaign["campaign"]["gauge"]

        def _call_contracts():
            # YB vote_user_slopes returns 4 values: (slope, bias, power, end)
            # Standard returns 3 values: (slope, power, end)
            if is_yb:
                slope, bias, power, end = (
                    gauge_controller.functions.vote_user_slopes(
                        to_checksum_address(user_address),
                        to_checksum_address(gauge_address),
                    ).call()
                )
            else:
                slope, power, end = (
                    gauge_controller.functions.vote_user_slopes(
                        to_checksum_address(user_address),
                        to_checksum_address(gauge_address),
                    ).call()
                )
                bias = 0
            last_vote = gauge_controller.functions.last_user_vote(
                to_checksum_address(user_address),
                to_checksum_address(gauge_address),
            ).call()
            return {
                "slope": int(slope),
                "bias": int(bias),
                "power": int(power),
                "end": int(end),
                "last_vote": int(last_vote),
            }

        try:
            vote_data = await loop.run_in_executor(None, _call_contracts)
        except Exception:
            return None

        # YB infinite lock (perma lock): use bias as effective slope when end == MAX_UINT256
        effective_slope = vote_data["slope"]
        if is_yb and vote_data["end"] == MAX_UINT256 and vote_data["bias"] > 0:
            effective_slope = vote_data["bias"]

        if effective_slope <= 0:
            return None

        total_periods = campaign.get("campaign", {}).get(
            "number_of_periods", len(campaign.get("periods", []))
        )

        return {
            "id": campaign["id"],
            "gauge": gauge_address,
            "is_closed": campaign.get("is_closed", False),
            "periods": total_periods,
            "slope": effective_slope,
            "power": vote_data["power"],
            "end": vote_data["end"],
            "last_vote": vote_data["last_vote"],
            "is_active_vote": vote_data["end"] > now
            or vote_data["end"] == MAX_UINT256,
        }

    tasks = [fetch_vote_data(campaign) for campaign in campaigns]
    vote_entries = [
        entry for entry in await asyncio.gather(*tasks) if entry is not None
    ]

    if not vote_entries:
        rprint(
            "[yellow]No campaigns found with an active vote slope for this user.[/yellow]"
        )
        return []

    vote_entries.sort(
        key=lambda item: (
            item["is_closed"],
            not item["is_active_vote"],
            -item["slope"],
            item["id"],
        )
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Campaign", style="yellow", width=9)
    table.add_column("Status", style="magenta", width=8)
    table.add_column("Gauge", style="white")
    table.add_column("Periods", style="green", width=8, justify="right")
    table.add_column("Slope", style="blue", width=14, justify="right")
    table.add_column("Vote Ends", style="white", width=16)
    table.add_column("Last Vote", style="white", width=16)
    table.add_column("Active", style="green", width=8)

    for idx, campaign in enumerate(vote_entries, start=1):
        status = "[green]ACTIVE[/green]"
        if campaign["is_closed"]:
            status = "[dim]CLOSED[/dim]"

        vote_end = (
            format_timestamp(campaign["end"]) if campaign["end"] > 0 else "N/A"
        )
        last_vote = (
            format_timestamp(campaign["last_vote"])
            if campaign["last_vote"] > 0
            else "N/A"
        )
        active_vote = (
            "[green]Yes[/green]"
            if campaign["is_active_vote"]
            else "[dim]No[/dim]"
        )

        table.add_row(
            str(idx),
            f"#{campaign['id']}",
            status,
            format_address(campaign["gauge"]),
            str(campaign["periods"]),
            f"{campaign['slope']:,.0f}",
            vote_end,
            last_vote,
            active_vote,
        )

    console.print(table)
    rprint(
        f"[dim]Found {len(vote_entries)} campaign(s) with a recorded vote for this user.[/dim]"
    )
    return vote_entries


def _prompt_campaign_from_available(
    available_campaigns: List[Dict[str, Any]],
) -> int:
    """Prompt the user to choose a campaign from the pre-filtered list."""
    if not available_campaigns:
        raise ValueError("No campaigns available for selection.")

    default_choice = str(available_campaigns[0]["id"])
    rprint("\n[cyan]Select a campaign to inspect in detail:[/cyan]")
    rprint(
        "[dim]Enter a campaign ID or the row number from the table above.[/dim]"
    )

    while True:
        try:
            choice = Prompt.ask("Campaign ID", default=default_choice).strip()
        except (KeyboardInterrupt, EOFError):
            rprint("\n[yellow]Selection cancelled[/yellow]")
            sys.exit(0)

        if choice.lower() in {"q", "quit", "exit"}:
            rprint("\n[yellow]Selection cancelled[/yellow]")
            sys.exit(0)

        if choice.isdigit():
            numeric_choice = int(choice)
            # Direct ID match
            for campaign in available_campaigns:
                if campaign["id"] == numeric_choice:
                    return campaign["id"]
            # Row index match
            if 1 <= numeric_choice <= len(available_campaigns):
                return available_campaigns[numeric_choice - 1]["id"]

        rprint(
            "[red]Invalid selection.[/red] Please enter a valid campaign ID or row number."
        )


async def check_user_campaign_status(
    chain_id: int,
    platform_address: str,
    campaign_ids: List[int],
    user_address: str,
    output_format: str = "table",
    brief: bool = False,
) -> None:
    """
    Check and display proof insertion status for a user in specific campaigns.

    Args:
        chain_id: Chain ID (1 for Ethereum, 42161 for Arbitrum)
        platform_address: VoteMarket platform contract address
        campaign_ids: List of Campaign IDs to check
        user_address: User address to check proofs for
        output_format: Output format (table, json)
        brief: Show brief output only
    """
    all_results = []

    for campaign_id in campaign_ids:
        try:
            # Fetch the specific campaign
            if not brief and output_format == "table":
                rprint(
                    Panel(
                        f"Fetching Campaign #{campaign_id} Details",
                        style="bold cyan",
                    )
                )

            campaigns = await campaign_service.get_campaigns(
                chain_id=chain_id,
                platform_address=platform_address,
                campaign_id=campaign_id,
                check_proofs=True,
            )

            if not campaigns:
                # Try to get total campaign count for better error message
                try:
                    web3_service = campaign_service.get_web3_service(chain_id)
                    platform_contract = web3_service.get_contract(
                        to_checksum_address(platform_address.lower()),
                        "vm_platform",
                    )
                    total_campaigns = (
                        platform_contract.functions.campaignCount().call()
                    )

                    if output_format == "json":
                        result = {
                            "error": f"Campaign #{campaign_id} not found",
                            "suggestion": f"This platform has campaigns 0-{total_campaigns-1}",
                        }
                        all_results.append(result)
                    else:
                        rprint(
                            f"[red]Error:[/red] Campaign #{campaign_id} not found"
                        )
                        rprint(
                            f"[yellow]This platform has campaigns 0-{total_campaigns-1}[/yellow]"
                        )
                except Exception:
                    # Failed to get total campaigns, just show the basic error
                    if output_format == "json":
                        all_results.append(
                            {"error": f"Campaign #{campaign_id} not found"}
                        )
                    else:
                        rprint(
                            f"[red]Error:[/red] Campaign #{campaign_id} not found"
                        )
                continue

            campaign = campaigns[0]

            # Get user proof status
            proof_status = (
                await campaign_service.get_user_campaign_proof_status(
                    chain_id=chain_id,
                    platform_address=platform_address,
                    campaign=campaign,
                    user_address=user_address,
                )
            )

            # Calculate summary
            total_periods = len(proof_status["periods"])
            claimable_periods = sum(
                1
                for p in proof_status["periods"]
                if p.get("block_updated")
                and p.get("point_data_inserted")
                and p.get("user_slope_inserted")
            )

            # Format output based on options
            if brief:
                # Brief mode - just show summary
                status = "✓" if claimable_periods == total_periods else "✗"
                rprint(
                    f"Campaign #{campaign_id}: User can claim {claimable_periods}/{total_periods} periods {status}"
                )

            elif output_format == "json":
                # JSON output
                result = {
                    "campaign_id": campaign_id,
                    "chain_id": chain_id,
                    "platform": platform_address,
                    "user": user_address,
                    "gauge": campaign["campaign"]["gauge"],
                    "total_periods": total_periods,
                    "claimable_periods": claimable_periods,
                    "fully_claimable": claimable_periods == total_periods,
                    "periods": proof_status["periods"],
                }
                all_results.append(result)

            else:
                # Full table output (default)
                # Display campaign info
                campaign_info = campaign["campaign"]
                rprint("\n[cyan]Campaign Information:[/cyan]")
                rprint(f"  • Gauge: {campaign_info['gauge']}")
                rprint(f"  • Manager: {campaign_info['manager']}")
                rprint(f"  • Reward Token: {campaign_info['reward_token']}")
                rprint(
                    f"  • Total Periods: {campaign_info['number_of_periods']}"
                )
                rprint(
                    f"  • Status: {'Closed' if campaign['is_closed'] else 'Active'}"
                )

                if not campaign.get("periods"):
                    rprint(
                        "[yellow]No periods found for this campaign[/yellow]"
                    )
                    continue

                rprint(
                    Panel(
                        f"Checking Proof Status for User: {format_address(user_address)}",
                        style="bold magenta",
                    )
                )

                # Create detailed status table
                table = _create_period_status_table(proof_status["periods"])

                # Display the table
                console.print(table)

                # Summary
                rprint("\n[cyan]Summary:[/cyan]")
                rprint(f"  • Total Periods: {total_periods}")
                rprint(f"  • Claimable Periods: {claimable_periods}")
                rprint(
                    f"  • Missing Proofs: {total_periods - claimable_periods}"
                )

                if claimable_periods == total_periods:
                    rprint(
                        "[green]✓ All proofs inserted - User can claim rewards![/green]"
                    )
                elif claimable_periods > 0:
                    rprint(
                        f"[yellow]⚠ Partial proofs available - User can claim {claimable_periods}/{total_periods} periods[/yellow]"
                    )
                else:
                    rprint(
                        "[red]✗ No proofs available - User cannot claim rewards yet[/red]"
                    )

                if proof_status.get("oracle_address"):
                    rprint(
                        f"\n[dim]Oracle Address: {proof_status['oracle_address']}[/dim]"
                    )

        except Exception as e:
            if output_format == "json":
                all_results.append(
                    {"campaign_id": campaign_id, "error": str(e)}
                )
            else:
                rprint(
                    f"[red]Error checking campaign #{campaign_id}:[/red] {str(e)}"
                )

    # Output JSON if requested
    if output_format == "json":
        print(json.dumps(all_results, indent=2))


def main():
    """Main entry point for the command."""
    parser = argparse.ArgumentParser(
        description="Check proof insertion status for a user in VoteMarket campaigns"
    )
    parser.add_argument(
        "--chain-id",
        type=int,
        required=False,
        help="Chain ID (auto-detected if not specified)",
    )
    parser.add_argument(
        "--platform",
        type=str,
        required=False,
        help="VoteMarket platform address (interactive selection if not provided)",
    )
    parser.add_argument(
        "--campaign-id",
        type=str,
        required=False,
        help="Campaign ID(s) to check (interactive selection if not provided)",
    )
    parser.add_argument(
        "--user",
        type=str,
        required=False,
        help="User address to check proofs for",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="Show brief output (summary only)",
    )
    parser.add_argument(
        "--list-available",
        action="store_true",
        help="List campaigns where the user currently has a vote recorded",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Force interactive mode for selections",
    )

    args = parser.parse_args()

    platform_metadata: Optional[Dict[str, Any]] = None

    # Interactive platform selection if not provided
    if not args.platform or args.interactive:
        # If chain is specified, use it as filter
        platform_metadata = select_platform(chain_id=args.chain_id)
        platform_address = platform_metadata["address"]
        chain_id = platform_metadata["chain_id"]
    else:
        # Validate and format platform address
        try:
            platform_address = to_checksum_address(args.platform.lower())
        except Exception as e:
            rprint(f"[red]Error:[/red] Invalid platform address: {e}")
            sys.exit(1)

        # Auto-detect chain if not provided
        chain_id = args.chain_id
        if not chain_id:
            chain_id = registry.get_chain_for_platform(platform_address)
            if not chain_id:
                rprint(
                    "[yellow]Unknown platform address. Please select a chain:[/yellow]"
                )
                chain_id = select_chain()
            elif args.format == "table" and not args.brief:
                chain_names = registry.get_supported_chains()
                chain_name = chain_names.get(
                    chain_id, f"Chain {chain_id}"
                ).title()
                rprint(f"[dim]Auto-detected chain: {chain_name}[/dim]")

        platform_metadata = _resolve_platform_metadata(
            chain_id, platform_address
        )

    platform_protocol = (
        platform_metadata.get("protocol") if platform_metadata else None
    )

    # Validate user address
    user_input = args.user.strip() if args.user else ""

    if args.interactive or not user_input:
        while True:
            try:
                prompt_message = (
                    "[cyan]Enter user address (0x...)[/cyan]"
                    if not user_input
                    else "[cyan]Confirm or update user address (0x...)[/cyan]"
                )
                user_response = (
                    Prompt.ask(prompt_message, default=user_input).strip()
                    if user_input
                    else Prompt.ask(prompt_message).strip()
                )
            except (KeyboardInterrupt, EOFError):
                rprint("\n[yellow]Operation cancelled[/yellow]")
                sys.exit(0)

            if user_response:
                user_input = user_response
                break

            rprint(
                "[yellow]A user address is required to continue. Please try again.[/yellow]"
            )

    try:
        user_address = to_checksum_address(user_input.lower())
    except Exception as e:
        rprint(f"[red]Error:[/red] Invalid user address: {e}")
        sys.exit(1)

    available_campaigns: List[Dict[str, Any]] = []
    if args.list_available:
        available_campaigns = asyncio.run(
            list_user_voted_campaigns(
                chain_id=chain_id,
                platform_address=platform_address,
                user_address=user_address,
                protocol=platform_protocol,
            )
        )

        if not args.campaign_id:
            if available_campaigns:
                try:
                    proceed = Prompt.ask(
                        "Check detailed status for one of these campaigns? [y/n]",
                        choices=["y", "n"],
                        default="y",
                    )
                except (KeyboardInterrupt, EOFError):
                    rprint("\n[yellow]Operation cancelled[/yellow]")
                    sys.exit(0)

                if proceed.lower() != "y":
                    return
            else:
                try:
                    proceed = Prompt.ask(
                        "No active votes found. Continue to select a campaign? [y/n]",
                        choices=["y", "n"],
                        default="n",
                    )
                except (KeyboardInterrupt, EOFError):
                    rprint("\n[yellow]Operation cancelled[/yellow]")
                    sys.exit(0)

                if proceed.lower() != "y":
                    return

    if args.campaign_id and not args.interactive:
        # Parse campaign IDs (support comma-separated list)
        try:
            campaign_ids = [
                int(cid.strip()) for cid in args.campaign_id.split(",")
            ]
        except ValueError:
            rprint(
                "[red]Error:[/red] Invalid campaign ID format. Use numbers separated by commas."
            )
            sys.exit(1)
    else:
        if available_campaigns:
            campaign_ids = [
                _prompt_campaign_from_available(available_campaigns)
            ]
        else:
            campaign_id = asyncio.run(
                select_campaign(chain_id, platform_address)
            )
            campaign_ids = [campaign_id]

    # Run the async function
    asyncio.run(
        check_user_campaign_status(
            chain_id=chain_id,
            platform_address=platform_address,
            campaign_ids=campaign_ids,
            user_address=user_address,
            output_format=args.format,
            brief=args.brief,
        )
    )


if __name__ == "__main__":
    main()
