import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import List, Optional

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from votemarket_toolkit.campaigns.services.campaign_service import (
    CampaignService,
)
from votemarket_toolkit.commands.validation import (
    validate_chain_id,
    validate_eth_address,
    validate_protocol,
)
from votemarket_toolkit.shared.constants import ContractRegistry

console = Console()


def get_campaign_status(campaign: dict) -> str:
    """
    Determine campaign status based on its state
    Returns colored status string for rich console
    """
    current_timestamp = int(datetime.now().timestamp())

    if campaign["is_closed"]:
        return "[red]Closed[/red]"
    elif campaign["details"]["end_timestamp"] < current_timestamp:
        return "[orange3]Inactive[/orange3]"  # Past end time but not closed
    else:
        return "[green]Active[/green]"


async def get_active_campaigns_for_platform(
    chain_id: int, platform: str, campaign_service: CampaignService
) -> List[dict]:
    """Get active campaigns for a specific chain/platform combination"""
    try:
        campaigns = await campaign_service.query_active_campaigns(
            chain_id, platform
        )
        return campaigns
    except Exception as e:
        console.print(
            f"[red]Error fetching campaigns for chain {chain_id}:"
            f" {str(e)}[/red]"
        )
        return []


def format_address(address: str, length: int = 10) -> str:
    """Format address to show start and end with ... in middle"""
    if not address:
        return ""
    if len(address) <= length:
        return address
    return f"{address[:6]}...{address[-4:]}"


async def get_all_active_campaigns(
    chain_id: Optional[int] = None,
    platform: Optional[str] = None,
    protocol: Optional[str] = None,
):
    """Get active campaigns across multiple chains/platforms"""
    campaign_service = CampaignService()

    # Determine which platforms to query
    platforms_to_query = []

    if protocol:
        # Get all platforms for the protocol
        all_platforms = campaign_service.get_all_platforms(protocol)
        platforms_to_query.extend(
            [(p["chain_id"], p["address"]) for p in all_platforms]
        )
    elif chain_id and platform:
        # Single chain/platform combination
        platforms_to_query.append((chain_id, platform))
    elif chain_id:
        # All platforms on a specific chain
        for protocol_name in ContractRegistry.PROTOCOLS:
            try:
                address = ContractRegistry.get_address(protocol_name, chain_id)
                platforms_to_query.append((chain_id, address))
            except ValueError:
                continue
    else:
        console.print(
            "[yellow]Please provide at least a chain-id or protocol[/yellow]"
        )
        return

    # Create tasks for all platforms
    tasks = [
        get_active_campaigns_for_platform(chain_id, platform, campaign_service)
        for chain_id, platform in platforms_to_query
    ]

    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks)

    # Prepare data for JSON output
    output_data = {
        "timestamp": int(datetime.now().timestamp()),
        "query": {
            "chain_id": chain_id,
            "platform": platform,
            "protocol": protocol,
        },
        "campaigns": [],
    }

    # Combine and display results
    table = Table(
        show_header=True,
        header_style="bold cyan",
        show_lines=True,
        pad_edge=False,
        collapse_padding=True,
    )

    # Simplified columns
    table.add_column("Chain", width=6)
    table.add_column("Gauge", width=14)
    table.add_column("Token", width=14)
    table.add_column("Status", width=10, justify="center")
    table.add_column("Left", width=5, justify="right")
    table.add_column("Total", width=12, justify="right")

    for (chain_id, platform), campaigns in zip(platforms_to_query, results):
        if campaigns:
            rprint(
                Panel(
                    f"Found {len(campaigns)} campaigns for Chain {chain_id},"
                    f" Platform {format_address(platform)}",
                    style="bold magenta",
                )
            )
            for c in campaigns:
                status = get_campaign_status(c)

                # Format amounts in readable format
                total_reward = (
                    f"{c['details']['total_reward_amount'] / 1e18:.2f}"
                )

                # Add to table
                table.add_row(
                    str(chain_id),
                    format_address(c["gauge"]),
                    format_address(c["reward_token"]),
                    status,
                    str(c["period_left"]),
                    total_reward,
                )

                # Add to output data
                output_data["campaigns"].append(
                    {
                        "chain_id": chain_id,
                        "platform": platform,
                        "campaign_id": c["id"],
                        "gauge": c["gauge"],
                        "manager": c["manager"],
                        "reward_token": c["reward_token"],
                        "is_closed": c["is_closed"],
                        "is_whitelist_only": c["is_whitelist_only"],
                        "period_left": c["period_left"],
                        "listed_users": c["listed_users"],
                        "details": c["details"],
                        "current_period": c["current_period"],
                    }
                )
        else:
            rprint(
                f"[yellow]No campaigns found for Chain {chain_id}, Platform"
                f" {platform}[/yellow]"
            )

    # Save to JSON file
    os.makedirs("temp", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"temp/active_campaigns_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(output_data, f, indent=2)

    # Display results
    rprint(table)
    rprint(f"\n[cyan]Campaign data saved to:[/cyan] {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Query active campaigns across chains/platforms"
    )
    parser.add_argument(
        "--chain-id",
        type=int,
        help="Chain ID (1 for Ethereum, 42161 for Arbitrum)",
    )
    parser.add_argument(
        "--platform",
        type=str,
        help="Platform address (e.g., 0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5)",
    )
    parser.add_argument(
        "--protocol", type=str, help="Protocol name (curve, balancer)"
    )

    args = parser.parse_args()

    try:
        # Validate chain ID if provided
        if args.chain_id:
            validate_chain_id(args.chain_id)

        # Validate platform address if provided
        if args.platform:
            args.platform = validate_eth_address(args.platform, "platform")

        # Validate protocol if provided
        if args.protocol:
            args.protocol = validate_protocol(args.protocol)

        # Run the async function
        asyncio.run(
            get_all_active_campaigns(
                chain_id=args.chain_id,
                platform=args.platform,
                protocol=args.protocol,
            )
        )

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
