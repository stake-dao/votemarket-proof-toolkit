from proofs.main import VoteMarketProofs
from rich import print as rprint
from rich.panel import Panel
import json
import os
import sys


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


if __name__ == "__main__":
    block_number = int(sys.argv[1])
    get_block_info(block_number)
