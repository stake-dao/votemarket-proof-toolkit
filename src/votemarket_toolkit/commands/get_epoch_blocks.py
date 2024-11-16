import sys

from data.main import VoteMarketDataService
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table


def get_epoch_blocks(chain_id: int, platform: str, epochs: list[int]):
    vm = VoteMarketDataService(chain_id)
    blocks = vm.get_epochs_block(chain_id, platform, epochs)

    rprint(
        Panel(
            f"Epoch - Block Number stored for Chain {chain_id}",
            style="bold magenta",
        )
    )

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Epoch")
    table.add_column("Block Number")

    for epoch, block in blocks.items():
        table.add_row(str(epoch), str(block))

    rprint(table)


if __name__ == "__main__":
    chain_id = int(sys.argv[1])
    platform = sys.argv[2]
    epochs = [int(e) for e in sys.argv[3].split(",")]
    get_epoch_blocks(chain_id, platform, epochs)
