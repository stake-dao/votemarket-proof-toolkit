"""List all campaigns on a VoteMarket platform and save to JSON."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from eth_utils import to_checksum_address
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from votemarket_toolkit.campaigns.service import campaign_service
from votemarket_toolkit.shared import registry
from votemarket_toolkit.utils.interactive import select_chain, select_platform


def format_address(addr: str) -> str:
    """Format address as 0x...abcd"""
    return f"{addr[:6]}...{addr[-4:]}" if addr else "N/A"


def format_timestamp(timestamp: int) -> str:
    """Format timestamp to readable date"""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


def save_campaigns_to_json(
    campaigns: list, chain_id: int, platform_address: str
) -> str:
    """Save campaigns data to JSON file with all available information."""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = (
        output_dir
        / f"campaigns_{chain_id}_{platform_address[:8]}_{timestamp}.json"
    )

    # Sort campaigns by ID
    sorted_campaigns = sorted(campaigns, key=lambda x: x.get("id", 0))

    # Enhance campaigns with formatted data
    for campaign in sorted_campaigns:
        # Add formatted dates
        if campaign.get("campaign"):
            camp = campaign["campaign"]
            campaign["formatted_start"] = datetime.fromtimestamp(
                camp["start_timestamp"]
            ).isoformat()
            campaign["formatted_end"] = datetime.fromtimestamp(
                camp["end_timestamp"]
            ).isoformat()

        # Ensure token information is properly structured
        if "reward_token" in campaign and "receipt_reward_token" in campaign:
            # Token info already enriched by service
            pass
        elif campaign.get("campaign", {}).get("reward_token"):
            # Fallback if token enrichment didn't happen
            token_addr = campaign["campaign"]["reward_token"]
            basic_token = {
                "address": token_addr,
                "name": "Unknown",
                "symbol": "???",
                "decimals": 18,
                "chain_id": chain_id,
                "price": 0.0,
            }
            campaign["reward_token"] = basic_token
            campaign["receipt_reward_token"] = basic_token

    # Prepare full data for JSON export
    export_data = {
        "metadata": {
            "chain_id": chain_id,
            "platform_address": platform_address,
            "timestamp": timestamp,
            "total_campaigns": len(sorted_campaigns),
            "active_campaigns": sum(
                1 for c in sorted_campaigns if not c.get("is_closed", False)
            ),
            "closed_campaigns": sum(
                1 for c in sorted_campaigns if c.get("is_closed", False)
            ),
        },
        "campaigns": sorted_campaigns,
    }

    with open(filename, "w") as f:
        json.dump(export_data, f, indent=2, default=str)

    return str(filename)


async def list_campaigns(
    chain_id: int,
    platform_address: str,
    output_format: str = "table",
    active_only: bool = False,
) -> None:
    """List all campaigns on a platform and save to JSON."""
    console = Console()

    try:
        rprint("[cyan]Fetching campaigns from platform...[/cyan]")

        campaigns = await campaign_service.get_campaigns(
            chain_id=chain_id,
            platform_address=platform_address,
            campaign_id=None,
            check_proofs=False,
        )

        if not campaigns:
            rprint("[yellow]No campaigns found on this platform[/yellow]")
            return

        # Save all campaigns to JSON file
        json_file = save_campaigns_to_json(
            campaigns, chain_id, platform_address
        )
        rprint(f"[green]✓ Full campaign data saved to: {json_file}[/green]")

        # Filter if needed for display
        display_campaigns = campaigns
        if active_only:
            display_campaigns = [
                c for c in campaigns if not c.get("is_closed", False)
            ]
            if not display_campaigns:
                rprint(
                    "[yellow]No active campaigns found (but all campaigns saved to JSON)[/yellow]"
                )
                return

        # Display output
        if output_format == "json":
            # Simple JSON output to console
            output = []
            for c in sorted(display_campaigns, key=lambda x: x.get("id", 0)):
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
                            c["status_info"].status.value
                            if c.get("status_info")
                            and hasattr(c.get("status_info"), "status")
                            else "unknown"
                        ),
                    }
                )
            print(json.dumps(output, indent=2))
        else:
            # Table output
            table = Table(
                title=f"Campaigns on Platform ({len(display_campaigns)} shown)",
                show_header=True,
                header_style="bold",
            )

            table.add_column("ID", style="cyan")
            table.add_column("Gauge", style="white")
            table.add_column("Manager", style="white")
            table.add_column("Periods", style="yellow")
            table.add_column("Start", style="green")
            table.add_column("End", style="red")
            table.add_column("Status", style="magenta")

            for c in sorted(display_campaigns, key=lambda x: x.get("id", 0)):
                camp = c["campaign"]
                status_info = c.get("status_info")

                if c.get("is_closed"):
                    status = "[dim]CLOSED[/dim]"
                elif status_info and hasattr(status_info, "status"):
                    status_val = status_info.status.value
                    status = (
                        f"[green]{status_val}[/green]"
                        if "active" in status_val.lower()
                        else f"[yellow]{status_val}[/yellow]"
                    )
                else:
                    status = "[dim]UNKNOWN[/dim]"

                table.add_row(
                    str(c["id"]),
                    format_address(camp["gauge"]),
                    format_address(camp["manager"]),
                    str(camp["number_of_periods"]),
                    format_timestamp(camp["start_timestamp"]),
                    format_timestamp(camp["end_timestamp"]),
                    status,
                )

            console.print(table)

            # Summary
            active = sum(
                1 for c in display_campaigns if not c.get("is_closed", False)
            )
            closed = len(display_campaigns) - active
            rprint(
                f"\n[cyan]Summary:[/cyan] Active: {active} | Closed: {closed}"
            )

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
        help="Chain ID (auto-detected if not specified)",
    )
    parser.add_argument(
        "--platform", type=str, help="VoteMarket platform address"
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format",
    )
    parser.add_argument(
        "--active-only", action="store_true", help="Show only active campaigns"
    )

    args = parser.parse_args()

    # Get platform info
    if not args.platform:
        platform_info = select_platform(chain_id=args.chain_id)
        platform_address = platform_info["address"]
        chain_id = platform_info["chain_id"]
    else:
        try:
            platform_address = to_checksum_address(args.platform.lower())
        except Exception as e:
            rprint(f"[red]Error:[/red] Invalid platform address: {e}")
            sys.exit(1)

        chain_id = args.chain_id or registry.get_chain_for_platform(
            platform_address
        )
        if not chain_id:
            rprint("[yellow]Unknown platform. Please select chain:[/yellow]")
            chain_id = select_chain()

    # Run async function
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
