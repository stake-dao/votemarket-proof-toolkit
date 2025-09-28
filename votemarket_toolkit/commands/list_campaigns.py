"""
List Campaigns Command - Display all campaigns on a VoteMarket platform

This command shows a summary of all campaigns on a platform, making it easy
to find campaign IDs and see their status at a glance.
"""

import asyncio
import json
import sys

from eth_utils import to_checksum_address
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from votemarket_toolkit.campaigns.service import campaign_service
from votemarket_toolkit.shared import registry
from votemarket_toolkit.utils.interactive import select_chain, select_platform


def format_address(addr: str) -> str:
    """Format address as 0x...abcd"""
    if not addr:
        return "N/A"
    return f"{addr[:6]}...{addr[-4:]}"


def format_timestamp(timestamp: int) -> str:
    """Format timestamp to readable date"""
    from datetime import datetime

    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d")


async def list_campaigns(
    chain_id: int,
    platform_address: str,
    output_format: str = "table",
    active_only: bool = False,
) -> None:
    """
    List all campaigns on a platform.

    Args:
        chain_id: Chain ID
        platform_address: VoteMarket platform contract address
        output_format: Output format (table or json)
        active_only: Show only active campaigns
    """
    console = Console()

    try:
        # Fetch all campaigns
        rprint("[cyan]Fetching campaigns from platform...[/cyan]")

        campaigns = await campaign_service.get_campaigns(
            chain_id=chain_id,
            platform_address=platform_address,
            campaign_id=None,  # Get all
            check_proofs=False,
        )

        if not campaigns:
            rprint("[yellow]No campaigns found on this platform[/yellow]")
            return

        # Filter if needed
        if active_only:
            campaigns = [c for c in campaigns if not c.get("is_closed", False)]
            if not campaigns:
                rprint("[yellow]No active campaigns found[/yellow]")
                return

        # Format output
        if output_format == "json":
            # JSON output with essential fields
            output = []
            for c in campaigns:
                output.append(
                    {
                        "id": c["id"],
                        "gauge": c["campaign"]["gauge"],
                        "manager": c["campaign"]["manager"],
                        "reward_token": c["campaign"]["reward_token"],
                        "periods": c["campaign"]["number_of_periods"],
                        "start": c["campaign"]["start_timestamp"],
                        "end": c["campaign"]["end_timestamp"],
                        "is_closed": c.get("is_closed", False),
                        "status": (
                            c["status_info"]["status"].value
                            if "status_info" in c
                            else "unknown"
                        ),
                    }
                )
            print(json.dumps(output, indent=2))

        else:
            # Table output
            table = Table(
                title=f"Campaigns on Platform ({len(campaigns)} total)",
                show_header=True,
                header_style="bold",
            )

            table.add_column("ID", style="cyan", width=6)
            table.add_column("Gauge", style="white", width=12)
            table.add_column("Manager", style="white", width=12)
            table.add_column("Periods", style="yellow", width=8)
            table.add_column("Start", style="green", width=11)
            table.add_column("End", style="red", width=11)
            table.add_column("Status", style="magenta", width=12)
            table.add_column("Can Close", style="blue", width=10)

            for c in campaigns:
                campaign_info = c["campaign"]
                status_info = c.get("status_info", {})

                # Format status
                if c.get("is_closed"):
                    status = "CLOSED"
                    status_style = "dim"
                elif status_info.get("status"):
                    status = status_info["status"].value
                    status_style = "green" if "ACTIVE" in status else "yellow"
                else:
                    status = "UNKNOWN"
                    status_style = "dim"

                # Can close info
                can_close = ""
                if not c.get("is_closed") and status_info.get("can_close"):
                    who = status_info.get("who_can_close", "")
                    if who == "manager_only":
                        can_close = "Manager"
                    elif who == "everyone":
                        can_close = "Anyone"

                table.add_row(
                    str(c["id"]),
                    format_address(campaign_info["gauge"]),
                    format_address(campaign_info["manager"]),
                    f"{campaign_info['number_of_periods']}",
                    format_timestamp(campaign_info["start_timestamp"]),
                    format_timestamp(campaign_info["end_timestamp"]),
                    f"[{status_style}]{status}[/{status_style}]",
                    can_close,
                )

            console.print(table)

            # Summary
            active_count = sum(
                1 for c in campaigns if not c.get("is_closed", False)
            )
            closed_count = len(campaigns) - active_count
            closable_count = sum(
                1
                for c in campaigns
                if not c.get("is_closed", False)
                and c.get("status_info", {}).get("can_close", False)
            )

            rprint("\n[cyan]Summary:[/cyan]")
            rprint(f"  • Active: {active_count}")
            rprint(f"  • Closed: {closed_count}")
            if closable_count > 0:
                rprint(f"  • Can be closed: {closable_count}")

    except Exception as e:
        rprint(f"[red]Error fetching campaigns:[/red] {str(e)}")


def main():
    """Main entry point for the command."""
    import argparse

    parser = argparse.ArgumentParser(
        description="List all campaigns on a VoteMarket platform"
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
        "--format",
        type=str,
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Show only active campaigns",
    )

    args = parser.parse_args()

    # Interactive platform selection if not provided
    if not args.platform:
        platform_info = select_platform(chain_id=args.chain_id)
        platform_address = platform_info["address"]
        chain_id = platform_info["chain_id"]
    else:
        # Validate platform address
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
            chain_names = {
                1: "Ethereum",
                42161: "Arbitrum",
                10: "Optimism",
                137: "Polygon",
                8453: "Base",
            }
            chain_name = chain_names.get(chain_id, f"Chain {chain_id}")
            if args.format == "table":
                rprint(f"[dim]Auto-detected chain: {chain_name}[/dim]")

    # Run the async function
    asyncio.run(
        list_campaigns(
            chain_id=chain_id,
            platform_address=platform_address,
            output_format=args.format,
            active_only=args.active_only,
        )
    )


if __name__ == "__main__":
    main()
