"""Example of how to query active campaigns for a platform."""

import os
from typing import List
from dotenv import load_dotenv
from shared.types import Campaign
from votes.main import VoteMarketVotes
from eth_utils import to_checksum_address
from rich import print as rprint
from rich.panel import Panel
from rich.console import Console

load_dotenv()

CHAIN_ID = 42161  # Arbitrum
PLATFORM_ADDRESS = to_checksum_address(
    "0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e".lower()
)

vm_votes = VoteMarketVotes(CHAIN_ID)
console = Console()


def main():
    """Query and display active campaigns for a platform."""
    rprint(Panel("Querying Active Campaigns", style="bold green"))

    active_campaigns: List[Campaign] = vm_votes.get_active_campaigns(
        CHAIN_ID, PLATFORM_ADDRESS
    )

    rprint(
        f"[cyan]Number of active campaigns:[/cyan] [yellow]{len(active_campaigns)}[/yellow]"
    )

    for campaign in active_campaigns:
        console.print(Panel(f"Campaign ID: {campaign['id']}", style="bold magenta"))
        console.print(f"[green]Chain ID:[/green] {campaign['chain_id']}")
        console.print(f"[green]Platform Address:[/green] {PLATFORM_ADDRESS}")
        console.print(f"[green]Gauge:[/green] {campaign['gauge']}")
        console.print(
            f"[green]Listed Users:[/green] {', '.join(campaign['listed_users'])}"
        )
        console.print()

    rprint(Panel("Active Campaigns Query Completed", style="bold green"))


if __name__ == "__main__":
    main()
