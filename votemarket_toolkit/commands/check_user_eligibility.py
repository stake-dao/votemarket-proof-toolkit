#!/usr/bin/env python3
"""Check user eligibility across all campaigns for a protocol."""

import asyncio
import sys
from datetime import datetime, timezone

from eth_utils import to_checksum_address
from rich import print as rprint
from rich.table import Table

from votemarket_toolkit.proofs.user_eligibility_service import (
    UserEligibilityService,
)
from votemarket_toolkit.shared.registry import get_supported_chains
from votemarket_toolkit.utils.formatters import console

# Derive chain names from registry and title-case them for display
CHAIN_NAMES = {
    cid: name.title() for cid, name in get_supported_chains().items()
}


async def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check user eligibility across all campaigns"
    )
    parser.add_argument(
        "--user", type=str, required=True, help="User address to check"
    )
    parser.add_argument(
        "--protocol",
        type=str,
        required=True,
        help="Protocol (curve, balancer, fxn, pendle)",
    )
    parser.add_argument(
        "--gauge",
        type=str,
        help="Specific gauge to check (optional, for closed campaigns)",
    )
    parser.add_argument(
        "--chain-id", type=int, help="Chain ID (default: check all chains)"
    )
    parser.add_argument(
        "--status",
        type=str,
        choices=["active", "closed", "all"],
        default="all",
        help="Filter by campaign status (default: all)",
    )

    args = parser.parse_args()

    # Validate inputs
    protocol = args.protocol.lower()
    user = to_checksum_address(args.user)

    rprint(f"\n[bold cyan]Checking eligibility for user: {user}[/bold cyan]")
    rprint(f"[bold cyan]Protocol: {protocol.upper()}[/bold cyan]\n")

    # Warning if no gauge specified
    if not args.gauge:
        rprint(
            "[yellow]⚠️  WARNING: Checking all campaigns can take several minutes![/yellow]"
        )
        rprint(
            "[yellow]   This will check hundreds of campaigns across all gauges.[/yellow]"
        )
        rprint(
            "[yellow]   For faster results, use --gauge to check a specific gauge.[/yellow]\n"
        )
        rprint("Tips for faster results:")
        rprint("  • Use --gauge <address> to check a specific gauge")
        rprint("  • Use --status active to only check active campaigns")
        rprint(
            "  • Check your voting history on the governance platform first\n"
        )

    # Use the service
    service = UserEligibilityService()

    try:
        results = await service.check_user_eligibility(
            user=user,
            protocol=protocol,
            chain_id=args.chain_id,
            gauge_address=args.gauge,
            status_filter=args.status,
        )

        # Display summary
        summary = results["summary"]
        if summary["total_campaigns_checked"] == 0:
            rprint(
                f"[yellow]No campaigns found for protocol {protocol}[/yellow]"
            )
            return

        rprint("[green]=== Summary ===[/green]")
        rprint(
            f"Total campaigns checked: {summary['total_campaigns_checked']}"
        )
        rprint(
            f"Campaigns with your votes: {summary['campaigns_with_eligibility']}"
        )
        rprint(f"Claimable periods: {summary['total_claimable_periods']}")

        # Display results by chain
        for chain_id, chain_data in results["chains"].items():
            chain_name = CHAIN_NAMES.get(chain_id, f"Chain {chain_id}")
            rprint(f"\n[yellow]{chain_name} Results:[/yellow]")

            for campaign in chain_data["campaigns"]:
                status = (
                    "[green]ACTIVE[/green]"
                    if not campaign["is_closed"]
                    else "[dim]CLOSED[/dim]"
                )
                rprint(f"\n{'='*80}")
                rprint(
                    f"Campaign #{campaign['id']} ({status}) - Gauge: {campaign['gauge'][:10]}..."
                )
                rprint(f"Manager: {campaign['manager'][:10]}...")
                rprint(f"Reward Token: {campaign['reward_token'][:10]}...")
                rprint(f"{'='*80}")

                # Create Rich table for periods
                table = Table(show_header=True, header_style="bold")
                table.add_column("Period", width=10)
                table.add_column("Epoch Date", width=22)
                table.add_column("Status", width=10)
                table.add_column("Has Proof", width=10)
                table.add_column("Claimable", width=10)
                table.add_column("Notes", width=30)

                for period in campaign["periods"]:
                    epoch_date = datetime.fromtimestamp(
                        period["epoch"], tz=timezone.utc
                    )
                    has_proof = (
                        "[green]✓[/green]"
                        if period["has_proof"]
                        else "[red]✗[/red]"
                    )
                    claimable = (
                        "[green]✓[/green]"
                        if period["claimable"]
                        else "[red]✗[/red]"
                    )
                    table.add_row(
                        f"#{period['period']}",
                        epoch_date.strftime("%Y-%m-%d %H:%M UTC"),
                        period["status"],
                        has_proof,
                        claimable,
                        period["reason"],
                    )

                console.print(table)

        if summary["campaigns_with_eligibility"] == 0:
            rprint(
                "\n[yellow]No campaigns found where user has votes or is eligible to claim[/yellow]"
            )

        rprint("\n[green]Check complete![/green]")

        if summary["total_claimable_periods"] > 0:
            rprint("\nTo generate proofs for claimable periods:")
            rprint(
                f"[cyan]  make user-proof USER={user} GAUGE=<gauge_address> PROTOCOL={protocol} BLOCK=<block_number>[/cyan]"
            )
            rprint("\nOr download pre-generated proofs from:")
            rprint(
                "[cyan]  https://github.com/stake-dao/api/tree/main/api/votemarket[/cyan]"
            )

    except Exception as e:
        rprint(f"\n[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        rprint("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        rprint(f"\n[red]Error: {e}[/red]")
        sys.exit(1)
