import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from rich import print as rprint
from rich.console import Console
from rich.table import Table

from votemarket_toolkit.campaigns import CampaignService
from votemarket_toolkit.commands.validation import (
    validate_chain_id,
    validate_eth_address,
    validate_protocol,
)
from votemarket_toolkit.shared import registry
from votemarket_toolkit.utils.pricing import (
    get_erc20_prices_in_usd,
    calculate_usd_per_vote,
    format_usd_value,
)

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
    end_timestamp = campaign["campaign"]["end_timestamp"]

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
    elif campaign["campaign"]["end_timestamp"] < current_timestamp:
        return "[orange3]Inactive[/orange3]"  # Past end time but not closed
    else:
        return "[green]Active[/green]"


async def get_active_campaigns_for_platform(
    chain_id: int,
    platform: str,
    campaign_service: CampaignService,
    check_proofs: bool = False,
) -> List[dict]:
    """Get active campaigns for a specific chain/platform combination."""
    try:
        campaigns = await campaign_service.get_campaigns(
            chain_id, platform, check_proofs=check_proofs
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
    check_proofs: bool = True,
):
    """Get active campaigns across multiple chains/platforms"""
    campaign_service = CampaignService()

    # Determine which platforms to query
    platforms_to_query = []

    if protocol and chain_id:
        # Get platforms for the protocol on a specific chain
        all_platforms = campaign_service.get_all_platforms(protocol)
        # Filter by chain_id
        filtered_platforms = [
            p for p in all_platforms if p["chain_id"] == chain_id
        ]
        platforms_to_query.extend(
            [(p["chain_id"], p["address"]) for p in filtered_platforms]
        )
    elif protocol:
        # Get all platforms for the protocol across all chains
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
        get_active_campaigns_for_platform(
            chain_id, platform, campaign_service, check_proofs
        )
        for chain_id, platform in platforms_to_query
    ]

    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks)

    # Prepare data for JSON output
    output_data = {
        "timestamp": int(datetime.now().timestamp()),
        "date": datetime.now().isoformat(),
        "query": {
            "chain_id": chain_id,
            "platform": platform,
            "protocol": protocol,
        },
        "campaigns": [],
        "summary": {
            "total_campaigns": 0,
            "active_campaigns": 0,
            "closed_campaigns": 0,
            "closable_by_anyone": 0,
            "closable_by_manager": 0,
            "total_rewards_allocated": 0,
            "total_rewards_distributed": 0,
            "campaigns_with_rewards": 0,
            "highest_avg_reward_per_vote": 0,
            "highest_avg_reward_campaign_id": None,
        },
    }

    # Process results by platform
    total_campaigns = 0
    platforms_with_campaigns = []

    # Collect unique reward tokens for price fetching
    token_price_cache = {}

    for (chain_id, platform), campaigns in zip(platforms_to_query, results):
        if campaigns:
            total_campaigns += len(campaigns)
            platforms_with_campaigns.append((chain_id, platform, campaigns))

            # Collect unique tokens for this chain
            unique_tokens = set()
            for c in campaigns:
                reward_token = c["campaign"].get("reward_token")
                if reward_token:
                    unique_tokens.add(reward_token.lower())

            # Fetch prices for all tokens on this chain
            if unique_tokens:
                print(
                    f"Fetching token prices for {len(unique_tokens)} tokens on chain {chain_id}..."
                )
                # Prepare batch request: list of (token_address, amount)
                # Using 1e18 as dummy amount since we only need unit price
                token_list = [(token, 10**18) for token in unique_tokens]
                prices_result = get_erc20_prices_in_usd(
                    chain_id, token_list, timestamp=None
                )

                # Store prices in cache (prices_result returns list of (formatted_str, float))
                for token, (_, price_float) in zip(unique_tokens, prices_result):
                    cache_key = f"{chain_id}:{token.lower()}"
                    if cache_key not in token_price_cache:
                        # The price_float is for 1 token (since we passed 10**18 wei)
                        token_price_cache[cache_key] = price_float

    # Display results split by platform
    for chain_id, platform, campaigns in platforms_with_campaigns:
        # Create a table for this platform
        rprint(
            f"\n[bold magenta]━━━ Platform: {format_address(platform)} | Chain: {chain_id} | Total: {len(campaigns)} ━━━[/bold magenta]"
        )

        table = Table(
            show_header=True,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
            box=None,
        )

        # Simplified columns
        table.add_column("ID", width=4, justify="right")
        table.add_column("Gauge", width=12)
        table.add_column("Token", width=12)
        table.add_column("Status", width=10, justify="center")
        table.add_column("Periods", width=8, justify="center")
        table.add_column("Total", width=10, justify="right")
        table.add_column("Closable", width=22)

        # Only show first 10 campaigns per platform to avoid clutter
        campaigns_to_show = (
            campaigns[:10] if len(campaigns) > 10 else campaigns
        )

        for c in campaigns_to_show:
            status = get_campaign_status(c)
            closability = get_closability_info(c)

            # Format amounts in readable format
            total_reward = f"{c['campaign']['total_reward_amount'] / 1e18:.2f}"

            # Count updated vs total periods
            updated_periods = sum(
                1 for p in c.get("periods", []) if p["updated"]
            )
            total_periods = len(c.get("periods", []))
            periods_display = f"{updated_periods}/{total_periods}"

            # Format closability status for display - shortened
            if closability["is_closable"]:
                if closability["can_be_closed_by"] == "Anyone":
                    # Extract days overdue
                    match = re.search(
                        r"(\d+)d", closability["closability_status"]
                    )
                    days = match.group(1) if match else "?"
                    closable_display = (
                        f"[bold yellow]Anyone ({days}d)[/bold yellow]"
                    )
                else:
                    # Manager closable
                    match = re.search(
                        r"(\d+)d", closability["closability_status"]
                    )
                    days = match.group(1) if match else "?"
                    closable_display = f"[cyan]Manager ({days}d)[/cyan]"
            elif "Active" in closability["closability_status"]:
                match = re.search(r"(\d+)d", closability["closability_status"])
                days = match.group(1) if match else "?"
                closable_display = f"[green]Active ({days}d)[/green]"
            elif "Claim Period" in closability["closability_status"]:
                match = re.search(r"(\d+)d", closability["closability_status"])
                days = match.group(1) if match else "?"
                closable_display = f"[dim]Claim ({days}d)[/dim]"
            else:
                closable_display = (
                    f"[dim]{closability['closability_status'][:20]}[/dim]"
                )

            # Add to table (without chain_id since it's in the header)
            table.add_row(
                str(c["id"]),
                format_address(c["campaign"]["gauge"]),
                format_address(c["campaign"]["reward_token"]),
                status,
                periods_display,
                total_reward[:10],  # Truncate large numbers
                closable_display,
            )

            # Get token price for USD calculations
            reward_token = c["campaign"].get("reward_token", "").lower()
            cache_key = f"{chain_id}:{reward_token}"
            token_price_usd = token_price_cache.get(cache_key, 0.0)

            # Process periods to include reward per vote details with USD values
            periods_with_rewards = []
            for idx, period in enumerate(c.get("periods", [])):
                period_data = {
                    "period_number": idx + 1,
                    "timestamp": period["timestamp"],
                    "date": datetime.fromtimestamp(
                        period["timestamp"]
                    ).strftime("%Y-%m-%d %H:%M"),
                    "reward_per_period": period["reward_per_period"],
                    "reward_per_period_ether": period["reward_per_period"]
                    / 1e18,
                    "reward_per_vote": period["reward_per_vote"],
                    "reward_per_vote_ether": period["reward_per_vote"] / 1e18,
                    "leftover": period["leftover"],
                    "leftover_ether": period["leftover"] / 1e18,
                    "updated": period["updated"],
                    "point_data_inserted": period.get(
                        "point_data_inserted", False
                    ),
                    "block_updated": period.get("block_updated", False),
                }

                # Calculate USD values
                if token_price_usd > 0:
                    period_data["reward_per_vote_usd"] = (
                        calculate_usd_per_vote(
                            period["reward_per_vote"], token_price_usd, 18
                        )
                    )
                    period_data["reward_per_period_usd"] = (
                        period["reward_per_period"] / 1e18
                    ) * token_price_usd
                else:
                    period_data["reward_per_vote_usd"] = 0.0
                    period_data["reward_per_period_usd"] = 0.0

                # Calculate distributed amount if period is updated
                if period["updated"]:
                    distributed = (
                        period["reward_per_period"] - period["leftover"]
                    )
                    period_data["distributed"] = distributed
                    period_data["distributed_ether"] = distributed / 1e18
                    if token_price_usd > 0:
                        period_data["distributed_usd"] = (
                            distributed / 1e18
                        ) * token_price_usd
                    else:
                        period_data["distributed_usd"] = 0.0
                else:
                    period_data["distributed"] = 0
                    period_data["distributed_ether"] = 0
                    period_data["distributed_usd"] = 0.0

                periods_with_rewards.append(period_data)

            # Calculate average reward per vote for non-zero periods
            non_zero_rewards = [
                p["reward_per_vote"]
                for p in periods_with_rewards
                if p["reward_per_vote"] > 0
            ]
            avg_reward_per_vote = (
                sum(non_zero_rewards) / len(non_zero_rewards)
                if non_zero_rewards
                else 0
            )

            # Calculate average USD per vote
            non_zero_usd_rewards = [
                p["reward_per_vote_usd"]
                for p in periods_with_rewards
                if p.get("reward_per_vote_usd", 0) > 0
            ]
            avg_reward_per_vote_usd = (
                sum(non_zero_usd_rewards) / len(non_zero_usd_rewards)
                if non_zero_usd_rewards
                else 0
            )

            # Add to output data with all periods info
            output_data["campaigns"].append(
                {
                    "chain_id": chain_id,
                    "platform": platform,
                    "campaign_id": c["id"],
                    "gauge": c["campaign"]["gauge"],
                    "manager": c["campaign"]["manager"],
                    "reward_token": c["campaign"]["reward_token"],
                    "reward_token_price_usd": token_price_usd,
                    "is_closed": c["is_closed"],
                    "is_whitelist_only": c["is_whitelist_only"],
                    "remaining_periods": c["remaining_periods"],
                    "whitelisted_addresses": c["addresses"],
                    "campaign_details": c["campaign"],
                    "current_epoch": c["current_epoch"],
                    "total_reward_amount": c["campaign"][
                        "total_reward_amount"
                    ],
                    "total_reward_amount_ether": c["campaign"][
                        "total_reward_amount"
                    ]
                    / 1e18,
                    "total_reward_amount_usd": (
                        c["campaign"]["total_reward_amount"] / 1e18
                    )
                    * token_price_usd
                    if token_price_usd > 0
                    else 0.0,
                    "max_reward_per_vote": c["campaign"][
                        "max_reward_per_vote"
                    ],
                    "max_reward_per_vote_ether": c["campaign"][
                        "max_reward_per_vote"
                    ]
                    / 1e18,
                    "max_reward_per_vote_usd": calculate_usd_per_vote(
                        c["campaign"]["max_reward_per_vote"],
                        token_price_usd,
                        18,
                    )
                    if token_price_usd > 0
                    else 0.0,
                    "average_reward_per_vote": avg_reward_per_vote,
                    "average_reward_per_vote_ether": avg_reward_per_vote
                    / 1e18,
                    "average_reward_per_vote_usd": avg_reward_per_vote_usd,
                    "periods": periods_with_rewards,
                    "closability": closability,
                }
            )

        # Display the table for this platform
        rprint(table)

        if len(campaigns) > 10:
            rprint(f"[dim]... and {len(campaigns) - 10} more campaigns[/dim]")

        # Add remaining campaigns to output_data (not displayed in table)
        for c in campaigns[10:]:
            status = get_campaign_status(c)
            closability = get_closability_info(c)

            # Get token price for USD calculations
            reward_token = c["campaign"].get("reward_token", "").lower()
            cache_key = f"{chain_id}:{reward_token}"
            token_price_usd = token_price_cache.get(cache_key, 0.0)

            # Process periods to include reward per vote details with USD values
            periods_with_rewards = []
            for idx, period in enumerate(c.get("periods", [])):
                period_data = {
                    "period_number": idx + 1,
                    "timestamp": period["timestamp"],
                    "date": datetime.fromtimestamp(
                        period["timestamp"]
                    ).strftime("%Y-%m-%d %H:%M"),
                    "reward_per_period": period["reward_per_period"],
                    "reward_per_period_ether": period["reward_per_period"]
                    / 1e18,
                    "reward_per_vote": period["reward_per_vote"],
                    "reward_per_vote_ether": period["reward_per_vote"] / 1e18,
                    "leftover": period["leftover"],
                    "leftover_ether": period["leftover"] / 1e18,
                    "updated": period["updated"],
                    "point_data_inserted": period.get(
                        "point_data_inserted", False
                    ),
                    "block_updated": period.get("block_updated", False),
                }

                # Calculate USD values
                if token_price_usd > 0:
                    period_data["reward_per_vote_usd"] = (
                        calculate_usd_per_vote(
                            period["reward_per_vote"], token_price_usd, 18
                        )
                    )
                    period_data["reward_per_period_usd"] = (
                        period["reward_per_period"] / 1e18
                    ) * token_price_usd
                else:
                    period_data["reward_per_vote_usd"] = 0.0
                    period_data["reward_per_period_usd"] = 0.0

                # Calculate distributed amount if period is updated
                if period["updated"]:
                    distributed = (
                        period["reward_per_period"] - period["leftover"]
                    )
                    period_data["distributed"] = distributed
                    period_data["distributed_ether"] = distributed / 1e18
                    if token_price_usd > 0:
                        period_data["distributed_usd"] = (
                            distributed / 1e18
                        ) * token_price_usd
                    else:
                        period_data["distributed_usd"] = 0.0
                else:
                    period_data["distributed"] = 0
                    period_data["distributed_ether"] = 0
                    period_data["distributed_usd"] = 0.0

                periods_with_rewards.append(period_data)

            # Calculate average reward per vote for non-zero periods
            non_zero_rewards = [
                p["reward_per_vote"]
                for p in periods_with_rewards
                if p["reward_per_vote"] > 0
            ]
            avg_reward_per_vote = (
                sum(non_zero_rewards) / len(non_zero_rewards)
                if non_zero_rewards
                else 0
            )

            # Calculate average USD per vote
            non_zero_usd_rewards = [
                p["reward_per_vote_usd"]
                for p in periods_with_rewards
                if p.get("reward_per_vote_usd", 0) > 0
            ]
            avg_reward_per_vote_usd = (
                sum(non_zero_usd_rewards) / len(non_zero_usd_rewards)
                if non_zero_usd_rewards
                else 0
            )

            output_data["campaigns"].append(
                {
                    "chain_id": chain_id,
                    "platform": platform,
                    "campaign_id": c["id"],
                    "gauge": c["campaign"]["gauge"],
                    "manager": c["campaign"]["manager"],
                    "reward_token": c["campaign"]["reward_token"],
                    "reward_token_price_usd": token_price_usd,
                    "is_closed": c["is_closed"],
                    "is_whitelist_only": c["is_whitelist_only"],
                    "remaining_periods": c["remaining_periods"],
                    "whitelisted_addresses": c["addresses"],
                    "campaign_details": c["campaign"],
                    "current_epoch": c["current_epoch"],
                    "total_reward_amount": c["campaign"][
                        "total_reward_amount"
                    ],
                    "total_reward_amount_ether": c["campaign"][
                        "total_reward_amount"
                    ]
                    / 1e18,
                    "total_reward_amount_usd": (
                        c["campaign"]["total_reward_amount"] / 1e18
                    )
                    * token_price_usd
                    if token_price_usd > 0
                    else 0.0,
                    "max_reward_per_vote": c["campaign"][
                        "max_reward_per_vote"
                    ],
                    "max_reward_per_vote_ether": c["campaign"][
                        "max_reward_per_vote"
                    ]
                    / 1e18,
                    "max_reward_per_vote_usd": calculate_usd_per_vote(
                        c["campaign"]["max_reward_per_vote"],
                        token_price_usd,
                        18,
                    )
                    if token_price_usd > 0
                    else 0.0,
                    "average_reward_per_vote": avg_reward_per_vote,
                    "average_reward_per_vote_ether": avg_reward_per_vote
                    / 1e18,
                    "average_reward_per_vote_usd": avg_reward_per_vote_usd,
                    "periods": periods_with_rewards,
                    "closability": closability,
                }
            )

    # Show summary
    if total_campaigns == 0:
        rprint("[yellow]No campaigns found[/yellow]")
    else:
        rprint(
            f"\n[bold green]Total campaigns found: {total_campaigns}[/bold green]"
        )

    # Calculate summary statistics
    if output_data["campaigns"]:
        output_data["summary"]["total_campaigns"] = len(
            output_data["campaigns"]
        )
        output_data["summary"]["active_campaigns"] = sum(
            1 for c in output_data["campaigns"] if not c["is_closed"]
        )
        output_data["summary"]["closed_campaigns"] = sum(
            1 for c in output_data["campaigns"] if c["is_closed"]
        )
        output_data["summary"]["closable_by_anyone"] = sum(
            1
            for c in output_data["campaigns"]
            if c["closability"]["can_be_closed_by"] == "Anyone"
        )
        output_data["summary"]["closable_by_manager"] = sum(
            1
            for c in output_data["campaigns"]
            if c["closability"]["can_be_closed_by"] == "Manager Only"
        )
        output_data["summary"]["total_rewards_allocated"] = sum(
            c["total_reward_amount_ether"] for c in output_data["campaigns"]
        )

        # Calculate total distributed
        total_distributed = 0
        for campaign in output_data["campaigns"]:
            for period in campaign["periods"]:
                if period["updated"]:
                    total_distributed += period.get("distributed_ether", 0)
        output_data["summary"]["total_rewards_distributed"] = total_distributed

        # Find campaign with highest average reward per vote
        campaigns_with_rewards = [
            c
            for c in output_data["campaigns"]
            if c["average_reward_per_vote"] > 0
        ]
        output_data["summary"]["campaigns_with_rewards"] = len(
            campaigns_with_rewards
        )

        if campaigns_with_rewards:
            best_campaign = max(
                campaigns_with_rewards,
                key=lambda x: x["average_reward_per_vote"],
            )
            output_data["summary"]["highest_avg_reward_per_vote"] = (
                best_campaign["average_reward_per_vote_ether"]
            )
            output_data["summary"]["highest_avg_reward_campaign_id"] = (
                best_campaign["campaign_id"]
            )

    # Save to JSON file in output directory
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create filename with protocol/chain info if available
    if protocol and chain_id:
        filename = f"output/active_campaigns_{protocol}_chain{chain_id}_{timestamp}.json"
    elif protocol:
        filename = f"output/active_campaigns_{protocol}_{timestamp}.json"
    elif chain_id:
        filename = f"output/active_campaigns_chain{chain_id}_{timestamp}.json"
    else:
        filename = f"output/active_campaigns_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(output_data, f, indent=2)

    # Show detailed period information for active campaigns
    active_campaigns = [
        c
        for c in output_data["campaigns"]
        if not c["is_closed"] and c["remaining_periods"] > 0
    ]
    if active_campaigns:
        rprint("\n[bold cyan]━━━ Active Campaign Periods ━━━[/bold cyan]")
        for campaign in active_campaigns[
            :5
        ]:  # Show details for first 5 active campaigns
            rprint(
                f"\n[cyan]Campaign #{campaign['campaign_id']}[/cyan] - {format_address(campaign['gauge'])}"
            )

            # Create a periods table
            period_table = Table(
                show_header=True, header_style="bold", box=None, padding=(0, 1)
            )
            period_table.add_column("Epoch", width=12)
            period_table.add_column("Date", width=10)
            period_table.add_column("Reward", width=12, justify="right")
            period_table.add_column("Per Vote", width=10, justify="right")
            period_table.add_column("$/Vote", width=12, justify="right")
            period_table.add_column("Updated", width=7, justify="center")

            # Add proof column if proof data is available
            has_proof_data = any(
                "point_data_inserted" in p for p in campaign["periods"]
            )
            if has_proof_data:
                period_table.add_column("Proof", width=5, justify="center")

            for period in campaign["periods"][-5:]:  # Show last 5 periods
                epoch_date = datetime.fromtimestamp(
                    period["timestamp"]
                ).strftime("%Y-%m-%d")
                reward = f"{period.get('reward_per_period_ether', period.get('reward_per_period', 0) / 1e18):.2f}"

                # Format reward per vote with better precision
                rpv = period.get(
                    "reward_per_vote_ether",
                    period.get("reward_per_vote", 0) / 1e18,
                )
                if rpv > 0:
                    if rpv < 0.0001:
                        per_vote = f"{rpv:.8f}"
                    elif rpv < 0.01:
                        per_vote = f"{rpv:.6f}"
                    else:
                        per_vote = f"{rpv:.4f}"
                else:
                    per_vote = "-"

                # Format USD per vote
                usd_per_vote = period.get("reward_per_vote_usd", 0.0)
                if usd_per_vote > 0:
                    usd_display = format_usd_value(usd_per_vote)
                else:
                    usd_display = "-"

                updated = "✓" if period.get("updated", False) else "✗"

                row_data = [
                    str(period["timestamp"]),
                    epoch_date,
                    reward,
                    per_vote,
                    usd_display,
                    updated,
                ]

                if has_proof_data:
                    proof_inserted = period.get("point_data_inserted", False)
                    proof_status = (
                        "[green]✓[/green]"
                        if proof_inserted
                        else "[red]✗[/red]"
                    )
                    row_data.append(proof_status)

                period_table.add_row(*row_data)

            rprint(period_table)

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
                    f"   • Campaign #{c['campaign_id']} on chain {c['chain_id']} - {format_address(c.get('gauge', c.get('campaign_details', {}).get('gauge', 'Unknown')))}"
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
                    f"   • Campaign #{c['campaign_id']} on chain {c['chain_id']} - {format_address(c.get('gauge', c.get('campaign_details', {}).get('gauge', 'Unknown')))}"
                )
                if days_until_anyone > 0:
                    rprint(
                        f"     [dim]{days_until_anyone} days until anyone can close[/dim]"
                    )

    rprint(f"\n[cyan]Campaign data saved to:[/cyan] {filename}")

    # Show summary of saved data
    if output_data["summary"]["total_campaigns"] > 0:
        rprint("\n[bold green]📊 Data Summary:[/bold green]")
        rprint(
            f"  • Total campaigns: {output_data['summary']['total_campaigns']}"
        )
        rprint(
            f"  • Total rewards allocated: {output_data['summary']['total_rewards_allocated']:.2f} ETH"
        )
        rprint(
            f"  • Total rewards distributed: {output_data['summary']['total_rewards_distributed']:.2f} ETH"
        )

        if output_data["summary"]["highest_avg_reward_campaign_id"]:
            rprint(
                f"  • Best avg reward/vote: Campaign #{output_data['summary']['highest_avg_reward_campaign_id']} "
            )
            rprint(
                f"    ({output_data['summary']['highest_avg_reward_per_vote']:.6f} tokens/vote)"
            )

        # Check if we have USD data
        campaigns_with_usd = [
            c
            for c in output_data["campaigns"]
            if c.get("reward_token_price_usd", 0) > 0
        ]
        if campaigns_with_usd:
            best_usd_campaign = max(
                campaigns_with_usd,
                key=lambda x: x.get("average_reward_per_vote_usd", 0),
            )
            if best_usd_campaign.get("average_reward_per_vote_usd", 0) > 0:
                rprint(
                    f"  • Best USD reward/vote: Campaign #{best_usd_campaign['campaign_id']}"
                )
                rprint(
                    f"    ({format_usd_value(best_usd_campaign['average_reward_per_vote_usd'])} per vote)"
                )

        rprint(
            "\n[dim]Note: All period data including reward_per_vote and USD values is saved in the JSON file[/dim]"
        )


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
    parser.add_argument(
        "--check-proofs",
        action="store_true",
        help="Check proof insertion status for each period (slower but more detailed)",
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
                check_proofs=args.check_proofs,
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
