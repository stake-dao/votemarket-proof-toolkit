import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

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
from votemarket_toolkit.shared import registry

console = Console()

# Constants for closability calculation
CLAIM_DEADLINE_MONTHS = 6  # 6 months claim period
CLOSE_WINDOW_MONTHS = 1  # 1 month close window after claim period
TOTAL_MONTHS = CLAIM_DEADLINE_MONTHS + CLOSE_WINDOW_MONTHS  # 7 months total


def calculate_deadlines(end_timestamp: int) -> Dict[str, Any]:
    """Calculate the claim deadline and close window timestamps."""
    end_date = datetime.fromtimestamp(end_timestamp)

    # Calculate 6 months after end (start of close window)
    claim_deadline = end_date + timedelta(days=30 * CLAIM_DEADLINE_MONTHS)

    # Calculate 7 months after end (end of close window)
    close_window_end = end_date + timedelta(days=30 * TOTAL_MONTHS)

    current_time = datetime.now()

    return {
        "end_date": end_date,
        "claim_deadline": claim_deadline,
        "close_window_end": close_window_end,
        "current_time": current_time,
        "is_within_close_window": claim_deadline
        <= current_time
        < close_window_end,
        "is_after_close_window": current_time >= close_window_end,
        "days_since_end": (current_time - end_date).days,
        "days_since_claim_deadline": (
            (current_time - claim_deadline).days
            if current_time >= claim_deadline
            else 0
        ),
        "days_until_anyone_can_close": (
            (close_window_end - current_time).days
            if claim_deadline <= current_time < close_window_end
            else 0
        ),
    }


def get_closability_info(campaign: dict) -> Dict[str, Any]:
    """
    Determine if campaign is closable and by whom.
    Returns dict with closability information.
    """
    current_timestamp = int(datetime.now().timestamp())
    end_timestamp = campaign["details"]["end_timestamp"]

    closability = {
        "is_closable": False,
        "can_be_closed_by": None,
        "funds_go_to": None,
        "days_until_closable": None,
        "closability_status": None,
    }

    # If campaign is already closed
    if campaign["is_closed"]:
        closability["closability_status"] = "Already Closed"
        return closability

    # If campaign hasn't ended yet
    if end_timestamp >= current_timestamp:
        days_until_end = (end_timestamp - current_timestamp) // 86400
        closability["closability_status"] = f"Active ({days_until_end}d left)"
        return closability

    # Calculate deadlines
    deadlines = calculate_deadlines(end_timestamp)

    # If within 6 months of end (claim period)
    if deadlines["days_since_end"] < (CLAIM_DEADLINE_MONTHS * 30):
        days_until_closable = (CLAIM_DEADLINE_MONTHS * 30) - deadlines[
            "days_since_end"
        ]
        closability["closability_status"] = (
            f"Claim Period ({days_until_closable}d until closable)"
        )
        closability["days_until_closable"] = days_until_closable
        return closability

    # If within close window (6-7 months after end)
    if deadlines["is_within_close_window"]:
        closability["is_closable"] = True
        closability["can_be_closed_by"] = "Manager Only"
        closability["funds_go_to"] = "Manager"
        closability["closability_status"] = (
            f"Closable by Manager ({deadlines['days_until_anyone_can_close']}d until anyone)"
        )
        return closability

    # If after close window (>7 months after end)
    if deadlines["is_after_close_window"]:
        closability["is_closable"] = True
        closability["can_be_closed_by"] = "Anyone"
        closability["funds_go_to"] = "Fee Collector"
        days_past_window = deadlines["days_since_claim_deadline"] - 30
        closability["closability_status"] = (
            f"Closable by Anyone ({days_past_window}d overdue)"
        )
        return closability

    return closability


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
        platforms = registry.get_platforms_for_chain(chain_id)
        for platform in platforms:
            platforms_to_query.append((chain_id, platform["address"]))
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

    # Simplified columns with campaign ID and closability
    table.add_column("ID", width=4, justify="right")
    table.add_column("Chain", width=6)
    table.add_column("Gauge", width=14)
    table.add_column("Token", width=14)
    table.add_column("Status", width=10, justify="center")
    table.add_column("Left", width=5, justify="right")
    table.add_column("Total", width=12, justify="right")
    table.add_column("Closable", width=25)

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
                closability = get_closability_info(c)

                # Format amounts in readable format
                total_reward = (
                    f"{c['details']['total_reward_amount'] / 1e18:.2f}"
                )

                # Format closability status for display
                closable_display = closability["closability_status"]
                if closability["is_closable"]:
                    if closability["can_be_closed_by"] == "Anyone":
                        closable_display = (
                            f"[bold yellow]{closable_display}[/bold yellow]"
                        )
                    else:
                        closable_display = f"[cyan]{closable_display}[/cyan]"
                else:
                    closable_display = f"[dim]{closable_display}[/dim]"

                # Add to table
                table.add_row(
                    str(c["id"]),
                    str(chain_id),
                    format_address(c["gauge"]),
                    format_address(c["reward_token"]),
                    status,
                    str(c["period_left"]),
                    total_reward,
                    closable_display,
                )

                # Add to output data with closability info
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
                        "current_period": c["current_period"], # TODO : Just use latest period from "periods"
                        "closability": closability,
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

    # Show summary of closable campaigns
    all_campaigns = output_data["campaigns"]
    closable_by_anyone = [
        c
        for c in all_campaigns
        if c["closability"]["can_be_closed_by"] == "Anyone"
    ]
    closable_by_manager = [
        c
        for c in all_campaigns
        if c["closability"]["can_be_closed_by"] == "Manager Only"
    ]

    if closable_by_anyone or closable_by_manager:
        rprint("\n[bold cyan]━━━ Closability Summary ━━━[/bold cyan]")

        if closable_by_anyone:
            rprint(
                f"\n[bold yellow]🚨 {len(closable_by_anyone)} campaigns can be closed by ANYONE:[/bold yellow]"
            )
            rprint("[yellow]   (funds go to fee collector)[/yellow]")
            for c in closable_by_anyone:
                rprint(
                    f"   • Campaign #{c['campaign_id']} on chain {c['chain_id']} - {format_address(c['gauge'])}"
                )
                rprint(f"     Platform: {format_address(c['platform'])}")
                rprint(
                    f"     [dim]To close: call closeCampaign({c['campaign_id']})[/dim]"
                )

        if closable_by_manager:
            rprint(
                f"\n[cyan]📅 {len(closable_by_manager)} campaigns can be closed by MANAGER ONLY:[/cyan]"
            )
            rprint("[cyan]   (funds return to manager)[/cyan]")
            for c in closable_by_manager:
                days_until_anyone = c["closability"].get(
                    "days_until_anyone_can_close", 0
                )
                rprint(
                    f"   • Campaign #{c['campaign_id']} on chain {c['chain_id']} - {format_address(c['gauge'])}"
                )
                if days_until_anyone > 0:
                    rprint(
                        f"     [dim]{days_until_anyone} days until anyone can close[/dim]"
                    )

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
