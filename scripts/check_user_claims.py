"""
Check user claims and unclaimed rewards across VoteMarket campaigns.

This script:
1. Finds all campaigns where the user has proofs (eligible to claim)
2. Checks on-chain if the user has already claimed for each epoch
3. Reports unclaimed rewards that can be claimed

Usage:
    python scripts/check_user_claims.py <user_address> [--protocol <protocol>] [--chain-id <chain_id>]
"""

import argparse
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional

from dotenv import load_dotenv
from eth_utils import to_checksum_address
from rich.console import Console
from rich.table import Table

from votemarket_toolkit.proofs.user_eligibility_service import UserEligibilityService
from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.services.web3_service import Web3Service

load_dotenv()

console = Console()


async def check_claimed_status(
    web3_service: Web3Service,
    platform_address: str,
    campaign_id: int,
    epoch: int,
    user_address: str,
) -> int:
    """
    Check if user has claimed for a specific campaign/epoch.

    Returns the amount claimed (0 if not claimed).
    """
    platform_contract = web3_service.get_contract(
        to_checksum_address(platform_address), "vm_platform"
    )

    loop = asyncio.get_running_loop()
    claimed_amount = await loop.run_in_executor(
        None,
        platform_contract.functions.totalClaimedByAccount(
            campaign_id, epoch, to_checksum_address(user_address)
        ).call,
    )

    return claimed_amount


async def check_user_unclaimed_rewards(
    user_address: str,
    protocol: Optional[str] = None,
    chain_id: Optional[int] = None,
) -> Dict:
    """
    Check all unclaimed rewards for a user.

    Returns a summary of unclaimed rewards by protocol/chain.
    """
    user_address = to_checksum_address(user_address)

    # Protocols to check
    protocols = [protocol] if protocol else ["curve", "balancer", "frax", "fxn", "pendle"]

    results = {
        "user": user_address,
        "timestamp": datetime.now().isoformat(),
        "unclaimed": [],
        "already_claimed": [],
        "summary": {
            "total_unclaimed_periods": 0,
            "total_already_claimed_periods": 0,
        },
    }

    async with UserEligibilityService() as eligibility_service:
        for proto in protocols:
            console.print(f"\n[cyan]Checking protocol: {proto}[/cyan]")

            try:
                # Get all campaigns where user has proofs
                eligibility_result = await eligibility_service.check_user_eligibility(
                    user=user_address,
                    protocol=proto,
                    chain_id=chain_id,
                    status_filter="all",
                )

                if not eligibility_result.get("chains"):
                    console.print(f"  [dim]No eligible campaigns found for {proto}[/dim]")
                    continue

                # Check claimed status for each eligible campaign/epoch
                for cid, chain_data in eligibility_result["chains"].items():
                    console.print(f"  [blue]Chain {cid}:[/blue]")

                    web3_service = Web3Service.get_instance(int(cid))
                    platforms = registry.get_all_platforms(proto)
                    platform_address = next(
                        (p["address"] for p in platforms if p["chain_id"] == int(cid)),
                        None
                    )

                    if not platform_address:
                        continue

                    for campaign in chain_data.get("campaigns", []):
                        campaign_id = campaign["id"]
                        gauge = campaign["gauge"]
                        reward_token = campaign["reward_token"]

                        unclaimed_periods = []
                        claimed_periods = []

                        for period in campaign.get("periods", []):
                            if not period.get("claimable"):
                                continue

                            epoch = period["epoch"]

                            # Check on-chain claimed status
                            claimed_amount = await check_claimed_status(
                                web3_service,
                                platform_address,
                                campaign_id,
                                epoch,
                                user_address,
                            )

                            if claimed_amount == 0:
                                unclaimed_periods.append({
                                    "epoch": epoch,
                                    "period": period["period"],
                                    "epoch_date": datetime.fromtimestamp(epoch).strftime("%Y-%m-%d"),
                                })
                            else:
                                claimed_periods.append({
                                    "epoch": epoch,
                                    "period": period["period"],
                                    "epoch_date": datetime.fromtimestamp(epoch).strftime("%Y-%m-%d"),
                                    "claimed_amount": claimed_amount,
                                })

                        if unclaimed_periods:
                            results["unclaimed"].append({
                                "protocol": proto,
                                "chain_id": int(cid),
                                "platform": platform_address,
                                "campaign_id": campaign_id,
                                "gauge": gauge,
                                "reward_token": reward_token,
                                "periods": unclaimed_periods,
                            })
                            results["summary"]["total_unclaimed_periods"] += len(unclaimed_periods)
                            console.print(
                                f"    [green]Campaign {campaign_id}: {len(unclaimed_periods)} unclaimed period(s)[/green]"
                            )

                        if claimed_periods:
                            results["already_claimed"].append({
                                "protocol": proto,
                                "chain_id": int(cid),
                                "platform": platform_address,
                                "campaign_id": campaign_id,
                                "gauge": gauge,
                                "reward_token": reward_token,
                                "periods": claimed_periods,
                            })
                            results["summary"]["total_already_claimed_periods"] += len(claimed_periods)

            except Exception as e:
                console.print(f"  [red]Error checking {proto}: {e}[/red]")
                continue

    return results


def print_results(results: Dict):
    """Print formatted results."""
    console.print("\n" + "=" * 70)
    console.print(f"[bold]UNCLAIMED REWARDS FOR {results['user']}[/bold]")
    console.print("=" * 70)

    if not results["unclaimed"]:
        console.print("\n[yellow]No unclaimed rewards found.[/yellow]")
        return

    # Create table
    table = Table(title="Unclaimed Periods")
    table.add_column("Protocol", style="cyan")
    table.add_column("Chain", style="blue")
    table.add_column("Campaign ID", style="magenta")
    table.add_column("Gauge", style="dim")
    table.add_column("Epoch Date", style="green")
    table.add_column("Epoch", style="dim")

    for item in results["unclaimed"]:
        for period in item["periods"]:
            table.add_row(
                item["protocol"],
                str(item["chain_id"]),
                str(item["campaign_id"]),
                item["gauge"][:10] + "...",
                period["epoch_date"],
                str(period["epoch"]),
            )

    console.print(table)

    console.print(f"\n[bold green]Total unclaimed periods: {results['summary']['total_unclaimed_periods']}[/bold green]")
    console.print(f"[dim]Already claimed periods: {results['summary']['total_already_claimed_periods']}[/dim]")

    # Print JSON for easy use
    console.print("\n[bold]JSON Data for claiming:[/bold]")
    claim_data = []
    for item in results["unclaimed"]:
        for period in item["periods"]:
            claim_data.append({
                "protocol": item["protocol"],
                "chain_id": item["chain_id"],
                "platform": item["platform"],
                "campaign_id": item["campaign_id"],
                "epoch": period["epoch"],
                "gauge": item["gauge"],
            })
    console.print(json.dumps(claim_data, indent=2))


async def main():
    parser = argparse.ArgumentParser(
        description="Check unclaimed VoteMarket rewards for a user"
    )
    parser.add_argument(
        "user_address",
        type=str,
        help="User wallet address to check",
    )
    parser.add_argument(
        "--protocol",
        type=str,
        choices=["curve", "balancer", "frax", "fxn", "pendle"],
        help="Specific protocol to check (optional, checks all if not specified)",
    )
    parser.add_argument(
        "--chain-id",
        type=int,
        help="Specific chain ID to check (optional)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path for JSON results",
    )

    args = parser.parse_args()

    console.print(f"\n[bold]Checking unclaimed rewards for: {args.user_address}[/bold]")

    results = await check_user_unclaimed_rewards(
        user_address=args.user_address,
        protocol=args.protocol,
        chain_id=args.chain_id,
    )

    print_results(results)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"\n[green]Results saved to {args.output}[/green]")


if __name__ == "__main__":
    asyncio.run(main())
