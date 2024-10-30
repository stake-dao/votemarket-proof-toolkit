from data.main import VoteMarketData
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table
import sys


def get_active_campaigns(chain_id: int, platform: str):
    vm = VoteMarketData(chain_id)
    rprint(
        Panel(f"Active Campaigns for Chain {chain_id}", style="bold magenta")
    )

    campaigns = vm.get_active_campaigns(chain_id, platform)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Campaign ID")
    table.add_column("Gauge")
    table.add_column("Listed Users")

    for c in campaigns:
        table.add_row(str(c["id"]), c["gauge"], str(len(c["listed_users"])))

    rprint(table)


if __name__ == "__main__":
    chain_id = int(sys.argv[1])
    platform = sys.argv[2]
    get_active_campaigns(chain_id, platform)
