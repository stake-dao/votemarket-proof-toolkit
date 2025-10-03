import argparse
import asyncio
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich import print as rprint
from rich.table import Table

from votemarket_toolkit.campaigns import CampaignService
from votemarket_toolkit.commands.validation import (
    validate_chain_id,
    validate_eth_address,
    validate_protocol,
)
from votemarket_toolkit.shared import registry
from votemarket_toolkit.utils.campaign_utils import (
    get_campaign_status,
    get_closability_info,
)
from votemarket_toolkit.utils.formatters import (
    console,
    format_address,
    generate_timestamped_filename,
    save_json_output,
)
from votemarket_toolkit.utils.pricing import (
    calculate_usd_per_vote,
    format_usd_value,
    get_erc20_prices_in_usd,
)


async def get_active_campaigns_for_platform(
    chain_id: int,
    platform: str,
    campaign_service: CampaignService,
    campaign_id: Optional[int] = None,
) -> List[dict]:
    """Get active campaigns for a specific chain/platform combination."""
    try:
        campaigns = await campaign_service.get_campaigns(
            chain_id, platform, campaign_id=campaign_id, check_proofs=True
        )
        return campaigns
    except Exception as e:
        console.print(
            f"[red]Error fetching campaigns for chain {chain_id}: {str(e)}[/red]"
        )
        return []


def _process_campaign_periods(
    campaign: dict, chain_id: int, token_price_usd: float
) -> tuple[List[Dict[str, Any]], float, float]:
    """
    Process campaign periods to calculate rewards and USD values.

    Returns:
        tuple: (periods_with_rewards, avg_reward_per_vote, avg_reward_per_vote_usd)
    """
    periods_with_rewards = []

    for idx, period in enumerate(campaign.get("periods", [])):
        period_data = {
            "period_number": idx + 1,
            "timestamp": period["timestamp"],
            "date": datetime.fromtimestamp(period["timestamp"]).strftime(
                "%Y-%m-%d %H:%M"
            ),
            "reward_per_period": period["reward_per_period"],
            "reward_per_period_ether": period["reward_per_period"] / 1e18,
            "reward_per_vote": period["reward_per_vote"],
            "reward_per_vote_ether": period["reward_per_vote"] / 1e18,
            "leftover": period["leftover"],
            "leftover_ether": period["leftover"] / 1e18,
            "updated": period["updated"],
            "point_data_inserted": period.get("point_data_inserted", False),
            "block_updated": period.get("block_updated", False),
        }

        # Calculate USD values
        if token_price_usd > 0:
            period_data["reward_per_vote_usd"] = calculate_usd_per_vote(
                period["reward_per_vote"], token_price_usd, 18
            )
            period_data["reward_per_period_usd"] = (
                period["reward_per_period"] / 1e18
            ) * token_price_usd
        else:
            period_data["reward_per_vote_usd"] = 0.0
            period_data["reward_per_period_usd"] = 0.0

        # Calculate distributed amount if period is updated
        if period["updated"]:
            distributed = period["reward_per_period"] - period["leftover"]
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

    return periods_with_rewards, avg_reward_per_vote, avg_reward_per_vote_usd


def _build_campaign_output_data(
    campaign: dict,
    chain_id: int,
    platform: str,
    periods_with_rewards: List[Dict],
    avg_reward_per_vote: float,
    avg_reward_per_vote_usd: float,
    token_price_usd: float,
    closability: Dict,
) -> Dict[str, Any]:
    """Build output data structure for a campaign."""
    # Get token info (enriched by service with symbol, name, etc.)
    reward_token_info = campaign.get("reward_token", {})
    receipt_token_info = campaign.get("receipt_reward_token", {})

    return {
        "chain_id": chain_id,
        "platform": platform,
        "campaign_id": campaign["id"],
        "gauge": campaign["campaign"]["gauge"],
        "manager": campaign["campaign"]["manager"],
        "reward_token": reward_token_info.get(
            "address", campaign["campaign"]["reward_token"]
        ),
        "reward_token_symbol": reward_token_info.get("symbol", "???"),
        "reward_token_name": reward_token_info.get("name", "Unknown"),
        "receipt_token": receipt_token_info.get(
            "address", campaign["campaign"]["reward_token"]
        ),
        "receipt_token_symbol": receipt_token_info.get("symbol", "???"),
        "reward_token_price_usd": token_price_usd,
        "is_closed": campaign["is_closed"],
        "is_whitelist_only": campaign["is_whitelist_only"],
        "remaining_periods": campaign["remaining_periods"],
        "whitelisted_addresses": campaign["addresses"],
        "campaign_details": campaign["campaign"],
        "current_epoch": campaign["current_epoch"],
        "total_reward_amount": campaign["campaign"]["total_reward_amount"],
        "total_reward_amount_ether": campaign["campaign"][
            "total_reward_amount"
        ]
        / 1e18,
        "total_reward_amount_usd": (
            (campaign["campaign"]["total_reward_amount"] / 1e18)
            * token_price_usd
            if token_price_usd > 0
            else 0.0
        ),
        "max_reward_per_vote": campaign["campaign"]["max_reward_per_vote"],
        "max_reward_per_vote_ether": campaign["campaign"][
            "max_reward_per_vote"
        ]
        / 1e18,
        "max_reward_per_vote_usd": (
            calculate_usd_per_vote(
                campaign["campaign"]["max_reward_per_vote"],
                token_price_usd,
                18,
            )
            if token_price_usd > 0
            else 0.0
        ),
        "average_reward_per_vote": avg_reward_per_vote,
        "average_reward_per_vote_ether": avg_reward_per_vote / 1e18,
        "average_reward_per_vote_usd": avg_reward_per_vote_usd,
        "periods": periods_with_rewards,
        "closability": closability,
    }


async def get_all_active_campaigns(
    chain_id: Optional[int] = None,
    platform: Optional[str] = None,
    protocol: Optional[str] = None,
    campaign_id: Optional[int] = None,
):
    """Get active campaigns across multiple chains/platforms"""
    campaign_service = CampaignService()

    # Determine which platforms to query
    platforms_to_query = []

    # If campaign_id is provided, we need at least protocol or (chain_id + platform)
    if campaign_id is not None:
        if not protocol and not (chain_id and platform):
            console.print(
                "[yellow]When using --campaign-id, provide either --protocol or both --chain-id and --platform[/yellow]"
            )
            return

    # Priority: platform > protocol > chain_id
    # If platform is specified, use only that platform (ignore protocol)
    if chain_id and platform:
        # Single chain/platform combination (most specific)
        platforms_to_query.append((chain_id, platform))
    elif protocol and chain_id:
        # Get platforms for the protocol on a specific chain
        all_platforms = campaign_service.get_all_platforms(protocol)
        # Filter by chain_id
        filtered_platforms = [
            p for p in all_platforms if p.chain_id == chain_id
        ]
        platforms_to_query.extend(
            [(p.chain_id, p.address) for p in filtered_platforms]
        )
    elif protocol:
        # Get all platforms for the protocol across all chains
        all_platforms = campaign_service.get_all_platforms(protocol)
        platforms_to_query.extend(
            [(p.chain_id, p.address) for p in all_platforms]
        )
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
            chain_id, platform, campaign_service, campaign_id
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
            "campaign_id": campaign_id,
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
            "total_periods_checked": 0,
            "total_periods_with_proofs": 0,
            "campaigns_with_all_proofs": 0,
            "campaigns_missing_proofs": 0,
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
                for token, (_, price_float) in zip(
                    unique_tokens, prices_result
                ):
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

            # Process periods and build output data
            (
                periods_with_rewards,
                avg_reward_per_vote,
                avg_reward_per_vote_usd,
            ) = _process_campaign_periods(c, chain_id, token_price_usd)

            # Add to output data
            output_data["campaigns"].append(
                _build_campaign_output_data(
                    c,
                    chain_id,
                    platform,
                    periods_with_rewards,
                    avg_reward_per_vote,
                    avg_reward_per_vote_usd,
                    token_price_usd,
                    closability,
                )
            )

        # Display the table for this platform
        rprint(table)

        if len(campaigns) > 10:
            rprint(f"[dim]... and {len(campaigns) - 10} more campaigns[/dim]")

            # Process remaining campaigns (not displayed in table)
            for c in campaigns[10:]:
                closability = get_closability_info(c)
                reward_token = c["campaign"].get("reward_token", "").lower()
                cache_key = f"{chain_id}:{reward_token}"
                token_price_usd = token_price_cache.get(cache_key, 0.0)

                (
                    periods_with_rewards,
                    avg_reward_per_vote,
                    avg_reward_per_vote_usd,
                ) = _process_campaign_periods(c, chain_id, token_price_usd)

                output_data["campaigns"].append(
                    _build_campaign_output_data(
                        c,
                        chain_id,
                        platform,
                        periods_with_rewards,
                        avg_reward_per_vote,
                        avg_reward_per_vote_usd,
                        token_price_usd,
                        closability,
                    )
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

        # Calculate proof statistics
        total_periods = 0
        periods_with_proofs = 0
        campaigns_with_all_proofs = 0
        campaigns_missing_proofs = 0

        for campaign in output_data["campaigns"]:
            campaign_periods = len(campaign["periods"])
            campaign_proofs = sum(
                1
                for p in campaign["periods"]
                if p.get("point_data_inserted", False)
            )
            total_periods += campaign_periods
            periods_with_proofs += campaign_proofs

            if campaign_periods > 0:
                if campaign_proofs == campaign_periods:
                    campaigns_with_all_proofs += 1
                elif campaign_proofs < campaign_periods:
                    campaigns_missing_proofs += 1

        output_data["summary"]["total_periods_checked"] = total_periods
        output_data["summary"][
            "total_periods_with_proofs"
        ] = periods_with_proofs
        output_data["summary"][
            "campaigns_with_all_proofs"
        ] = campaigns_with_all_proofs
        output_data["summary"][
            "campaigns_missing_proofs"
        ] = campaigns_missing_proofs

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

    # Create filename with protocol/chain info if available
    if campaign_id is not None:
        filename = generate_timestamped_filename(
            f"campaign_{campaign_id}_details"
        )
    elif protocol and chain_id:
        filename = generate_timestamped_filename(
            f"active_campaigns_{protocol}_chain{chain_id}"
        )
    elif protocol:
        filename = generate_timestamped_filename(
            f"active_campaigns_{protocol}"
        )
    elif chain_id:
        filename = generate_timestamped_filename(
            f"active_campaigns_chain{chain_id}"
        )
    else:
        filename = generate_timestamped_filename("active_campaigns")

    filepath = save_json_output(output_data, filename)

    # Show closability summary
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

    # Show summary of saved data
    if output_data["summary"]["total_campaigns"] > 0:
        rprint("\n[bold green]📊 Data Summary:[/bold green]")
        rprint(
            f"  • Total campaigns: {output_data['summary']['total_campaigns']}"
        )

        # Check if all campaigns use the same token
        unique_tokens = set(
            c["reward_token"] for c in output_data["campaigns"]
        )
        if len(unique_tokens) == 1:
            # All campaigns use same token - show totals with symbol
            campaign = output_data["campaigns"][0]
            token_symbol = campaign.get("reward_token_symbol", "tokens")
            token_name = campaign.get("reward_token_name", "Unknown")
            rprint(
                f"  • Total rewards allocated: {output_data['summary']['total_rewards_allocated']:.2f} {token_symbol}"
            )
            rprint(
                f"  • Total rewards distributed: {output_data['summary']['total_rewards_distributed']:.2f} {token_symbol}"
            )
            rprint(f"    [dim]({token_name})[/dim]")
        else:
            # Multiple different tokens - don't sum
            rprint(
                "  • [dim]Multiple reward tokens across campaigns (see JSON for details)[/dim]"
            )

        # Display proof statistics
        total_periods = output_data["summary"]["total_periods_checked"]
        periods_with_proofs = output_data["summary"][
            "total_periods_with_proofs"
        ]
        if total_periods > 0:
            proof_percentage = (periods_with_proofs / total_periods) * 100
            rprint(
                f"  • Proof coverage: {periods_with_proofs}/{total_periods} periods ({proof_percentage:.1f}%)"
            )
            rprint(
                f"  • Campaigns with all proofs: {output_data['summary']['campaigns_with_all_proofs']}"
            )
            if output_data["summary"]["campaigns_missing_proofs"] > 0:
                rprint(
                    f"  • Campaigns missing proofs: [yellow]{output_data['summary']['campaigns_missing_proofs']}[/yellow]"
                )

        if output_data["summary"]["highest_avg_reward_campaign_id"]:
            # Find the campaign with highest reward
            best_campaign_id = output_data["summary"][
                "highest_avg_reward_campaign_id"
            ]
            best_campaign = next(
                (
                    c
                    for c in output_data["campaigns"]
                    if c["campaign_id"] == best_campaign_id
                ),
                None,
            )
            if best_campaign:
                token_symbol = best_campaign.get(
                    "reward_token_symbol", "tokens"
                )
                rprint(
                    f"  • Best avg reward/vote: Campaign #{best_campaign_id}"
                )
                rprint(
                    f"    ({output_data['summary']['highest_avg_reward_per_vote']:.6f} {token_symbol}/vote)"
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
        "--campaign-id",
        type=int,
        help="Specific campaign ID to fetch (fetches all campaigns if not provided)",
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
                campaign_id=args.campaign_id,
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
