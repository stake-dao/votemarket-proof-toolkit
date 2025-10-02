import argparse
import sys
from typing import List

from rich.panel import Panel

from votemarket_toolkit.commands.helpers import handle_command_error
from votemarket_toolkit.commands.validation import (
    validate_chain_id,
    validate_eth_address,
)
from votemarket_toolkit.data import OracleService
from votemarket_toolkit.utils.formatters import (
    console,
    generate_timestamped_filename,
    save_json_output,
)


def get_epoch_blocks(chain_id: int, platform: str, epochs: List[int]):
    oracle_service = OracleService(chain_id)
    console.print(Panel("Fetching Epoch Blocks", style="bold magenta"))

    blocks = oracle_service.get_epochs_block(chain_id, platform, epochs)

    output_data = {
        "chain_id": chain_id,
        "platform": platform,
        "epochs": epochs,
        "blocks": blocks,
    }

    filename = generate_timestamped_filename("epoch_blocks")
    save_json_output(output_data, filename)

    console.print("[cyan]Epoch Blocks:[/cyan]")
    for epoch, block in blocks.items():
        console.print(f"Epoch {epoch}: Block {block}")


def main():
    parser = argparse.ArgumentParser(description="Get epoch blocks for a platform")
    parser.add_argument(
        "--chain-id",
        type=int,
        required=True,
        help="Chain ID (42161 for Arbitrum, 10 for Optimism, 137 for Polygon, 8453 for Base)",
    )
    parser.add_argument(
        "--platform",
        type=str,
        required=True,
        help="Platform address",
    )
    parser.add_argument(
        "--epochs",
        type=str,
        required=True,
        help="Comma-separated list of epoch numbers",
    )

    args = parser.parse_args()

    try:
        # Validate chain ID
        validate_chain_id(args.chain_id)

        # Validate platform address
        platform = validate_eth_address(args.platform, "platform")

        # Parse and validate epochs
        try:
            epochs = [int(e.strip()) for e in args.epochs.split(",")]
            if not epochs or any(e <= 0 for e in epochs):
                raise ValueError(
                    "EPOCHS must be a comma-separated list of positive integers"
                )
        except ValueError as e:
            raise ValueError(str(e))

        get_epoch_blocks(args.chain_id, platform, epochs)

    except (ValueError, Exception) as e:
        handle_command_error(e)


if __name__ == "__main__":
    main()
