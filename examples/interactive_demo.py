#!/usr/bin/env python3
"""
Interactive Mode Demo

This script demonstrates the interactive selection features of the VoteMarket toolkit.
Run it to see how easy it is to browse platforms and campaigns without memorizing addresses!
"""

import asyncio
import sys
from rich import print as rprint
from rich.panel import Panel

# Add parent directory to path for imports
sys.path.insert(0, "..")

from votemarket_toolkit.utils.interactive import (
    select_platform,
    select_chain,
    select_campaign,
)
from votemarket_toolkit.campaigns.service import campaign_service


async def demo():
    """Run the interactive demo."""

    rprint(
        Panel(
            "Welcome to VoteMarket Toolkit Interactive Demo", style="bold cyan"
        )
    )
    rprint(
        "\nThis demo shows how easy it is to browse and select platforms and campaigns."
    )
    rprint("No need to memorize addresses!\n")

    # Step 1: Select a platform
    rprint("[bold]Step 1:[/bold] Select a VoteMarket platform")
    platform_info = select_platform()

    rprint(
        f"\nYou selected: {platform_info['protocol'].upper()} on chain {platform_info['chain_id']}"
    )
    rprint(f"Platform address: {platform_info['address']}\n")

    # Step 2: Browse campaigns on that platform
    rprint("[bold]Step 2:[/bold] Browse campaigns on this platform")
    campaign_id = await select_campaign(
        chain_id=platform_info["chain_id"],
        platform_address=platform_info["address"],
    )

    rprint(f"\nYou selected campaign #{campaign_id}")

    # Step 3: Show what you can do next
    rprint("\n[bold]Step 3:[/bold] Now you can:")
    rprint("• Check if a user can claim rewards from this campaign")
    rprint("• View detailed campaign information")
    rprint("• Generate proofs for claiming")

    rprint("\n[green]Demo complete![/green]")
    rprint("\nTo check a user's status for this campaign, run:")
    rprint(
        f"[dim]make user-campaign-status PLATFORM={platform_info['address']} CAMPAIGN_ID={campaign_id} USER_ADDRESS=<your_address>[/dim]"
    )


if __name__ == "__main__":
    try:
        asyncio.run(demo())
    except KeyboardInterrupt:
        rprint("\n[yellow]Demo cancelled by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        rprint(f"\n[red]Error:[/red] {e}")
        sys.exit(1)
