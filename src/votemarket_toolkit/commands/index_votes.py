import asyncio
import sys
from datetime import datetime

from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.votes.services.votes_service import votes_service


async def index_votes(protocol: str, gauge_address: str):
    web3_service = Web3Service(1, "https://eth.llamarpc.com")
    # Current block number
    block_number = web3_service.get_latest_block()["number"]

    gauge_votes = await votes_service.get_gauge_votes(
        protocol, gauge_address, block_number
    )

    # Create a table
    table = Table(title=f"Votes for gauge {gauge_address}")

    # Add columns
    table.add_column("Time", justify="left", style="cyan")
    table.add_column("User", justify="left", style="green")
    table.add_column("Weight", justify="right", style="magenta")

    # Add rows
    for vote in gauge_votes.votes:
        # Convert timestamp to readable date
        date = datetime.fromtimestamp(vote.time).strftime("%Y-%m-%d %H:%M:%S")
        # Truncate user address
        user = f"{vote.user[:6]}...{vote.user[-4:]}"
        # Format weight as percentage
        weight = f"{vote.weight/100:.2f}%"

        table.add_row(date, user, weight)

    # Create a panel with the table and additional info
    panel = Panel(
        table,
        title="[bold blue]Gauge Votes Summary",
        subtitle=f"Latest Block: {gauge_votes.latest_block}",
    )

    rprint(panel)


if __name__ == "__main__":
    protocol = sys.argv[1]
    gauge_address = sys.argv[2]
    asyncio.run(index_votes(protocol, gauge_address))
