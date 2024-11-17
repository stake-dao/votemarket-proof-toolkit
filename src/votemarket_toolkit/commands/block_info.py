import json
import os
import sys

from rich import print as rprint
from rich.panel import Panel

from votemarket_toolkit.proofs.manager import VoteMarketProofs


def get_block_info(block_number: int):
    vm = VoteMarketProofs(1)
    rprint(Panel("Fetching Block Info", style="bold magenta"))

    info = vm.get_block_info(block_number)

    os.makedirs("temp", exist_ok=True)
    output_file = f"temp/block_info_{block_number}.json"

    with open(output_file, "w") as f:
        json.dump(info, f, indent=2)

    rprint("[cyan]Block Info saved to:[/cyan] " + output_file)
    rprint("[cyan]Block Info:[/cyan]")
    rprint(f'Block Number: {info["block_number"]}')
    rprint(f'Block Hash: {info["block_hash"]}')
    rprint(f'Block Timestamp: {info["block_timestamp"]}')
    rprint("[cyan]RLP Block Header:[/cyan]")
    rprint(f'[green]{info["rlp_block_header"]}[/green]')


def show_usage():
    rprint("[red]Error:[/red] Missing or invalid block number")
    rprint("\n[cyan]Required arguments:[/cyan]")
    rprint("- BLOCK_NUMBER: Positive integer representing the block number")
    rprint("\n[cyan]Example usage:[/cyan]")
    rprint("make block-info BLOCK_NUMBER=21203532")


def main():
    if len(sys.argv) != 2:
        show_usage()
        sys.exit(1)

    try:
        block_number = int(sys.argv[1])
        if block_number <= 0:
            raise ValueError("Block number must be a positive integer")

        get_block_info(block_number)

    except ValueError as e:
        rprint(f"[red]Error:[/red] {str(e)}")
        show_usage()
        sys.exit(1)
    except Exception as e:
        rprint(f"[red]Unexpected error:[/red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
