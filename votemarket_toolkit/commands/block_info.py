import argparse

from rich.panel import Panel

from votemarket_toolkit.commands.helpers import handle_command_error
from votemarket_toolkit.proofs.manager import VoteMarketProofs
from votemarket_toolkit.utils.formatters import console, save_json_output


def get_block_info(block_number: int):
    vm = VoteMarketProofs(1)
    console.print(Panel("Fetching Block Info", style="bold magenta"))

    info = vm.get_block_info(block_number)

    filename = f"block_info_{block_number}.json"
    save_json_output(info, filename)

    console.print("[cyan]Block Info:[/cyan]")
    console.print(f'Block Number: {info["block_number"]}')
    console.print(f'Block Hash: {info["block_hash"]}')
    console.print(f'Block Timestamp: {info["block_timestamp"]}')
    console.print("[cyan]RLP Block Header:[/cyan]")
    console.print(f'[green]{info["rlp_block_header"]}[/green]')


def main():
    parser = argparse.ArgumentParser(description="Get block information")
    parser.add_argument(
        "--block-number",
        type=int,
        required=True,
        help="Positive integer representing the block number",
    )

    args = parser.parse_args()

    try:
        if args.block_number <= 0:
            raise ValueError("Block number must be a positive integer")

        get_block_info(args.block_number)

    except (ValueError, Exception) as e:
        handle_command_error(e)


if __name__ == "__main__":
    main()
