"""Example of how to query voters for a gauge."""

import asyncio

from data.main import VoteMarketData
from dotenv import load_dotenv
from eth_utils import to_checksum_address
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel

load_dotenv()

vm_votes = VoteMarketData(1)
console = Console()

# Example parameters
PROTOCOL = "curve"
GAUGE_ADDRESS = to_checksum_address(
    "0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A".lower()
)  # sdCRV gauge
BLOCK_NUMBER = 20864159  # Max block number to check
CURRENT_EPOCH = 1723680000


async def main():
    """Query eligible users for a gauge."""
    rprint(Panel("Querying Eligible Users for Gauge", style="bold green"))

    # Query gauge votes
    rprint("[cyan]Fetching gauge votes...[/cyan]")
    gauge_votes = await vm_votes.get_gauge_votes(
        PROTOCOL, GAUGE_ADDRESS, BLOCK_NUMBER
    )
    rprint(f"[green]Found {len(gauge_votes)} gauge votes[/green]")

    # Get eligible users
    rprint("[cyan]Fetching eligible users...[/cyan]")
    eligible_users = await vm_votes.get_eligible_users(
        PROTOCOL, GAUGE_ADDRESS, CURRENT_EPOCH, BLOCK_NUMBER
    )

    rprint(
        f"[green]Found {len(eligible_users)} eligible users for gauge {GAUGE_ADDRESS}[/green]"
    )

    console.print("\n[bold magenta]Eligible Users:[/bold magenta]")
    for user in eligible_users[:5]:  # Display first 5 users as a sample
        console.print(
            Panel.fit(
                f"[yellow]User:[/yellow] {user['user']}\n"
                f"[yellow]Last Vote:[/yellow] {user['last_vote']}\n"
                f"[yellow]Slope:[/yellow] {user['slope']}\n"
                f"[yellow]Power:[/yellow] {user['power']}\n"
                f"[yellow]End:[/yellow] {user['end']}",
                title=f"User {eligible_users.index(user) + 1}",
                border_style="cyan",
            )
        )

    if len(eligible_users) > 5:
        rprint(f"[italic]...and {len(eligible_users) - 5} more users[/italic]")

    rprint(Panel("Query Completed", style="bold green"))


if __name__ == "__main__":
    asyncio.run(main())
