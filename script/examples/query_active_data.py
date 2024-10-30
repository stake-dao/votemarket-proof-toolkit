"""Example of how to query active campaigns for a platform."""

import time
from typing import List
from dotenv import load_dotenv
from shared.types import Campaign
from data.main import VoteMarketData
from eth_utils import to_checksum_address
from rich import print as rprint
from rich.panel import Panel
from rich.console import Console

from shared.utils import get_rounded_epoch

load_dotenv()

CHAIN_ID = 42161  # Arbitrum
PLATFORM_ADDRESS = to_checksum_address(
    "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5".lower()
)

vm_data = VoteMarketData(CHAIN_ID)
console = Console()


def main():
    """Query and display active campaigns for a platform."""
    rprint(Panel("Querying Active Votemarket Data", style="bold green"))

    # Active epoch
    current_timestamp = int(time.time())
    active_epoch = get_rounded_epoch(current_timestamp)

    # Latest blocks
    latest_block = vm_data.get_epochs_block(
        CHAIN_ID, PLATFORM_ADDRESS, [active_epoch]
    )[active_epoch]

    rprint(f"[cyan]Active epoch:[/cyan] [yellow]{active_epoch}[/yellow]")
    rprint(f"[cyan]Latest block:[/cyan] [yellow]{latest_block}[/yellow]")

    active_campaigns: List[Campaign] = vm_data.get_active_campaigns(
        CHAIN_ID, PLATFORM_ADDRESS
    )

    rprint(
        f"[cyan]Number of active campaigns:[/cyan] [yellow]{len(active_campaigns)}[/yellow]"
    )

    for campaign in active_campaigns:
        console.print(
            Panel(f"Campaign ID: {campaign['id']}", style="bold magenta")
        )
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
