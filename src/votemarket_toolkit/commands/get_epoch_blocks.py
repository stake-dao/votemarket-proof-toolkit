import argparse
import json
import os
import sys
from datetime import datetime
from typing import List

from rich import print as rprint
from rich.panel import Panel

from votemarket_toolkit.campaigns.services.data_service import (
    VoteMarketDataService,
)
from votemarket_toolkit.commands.validation import (
    validate_chain_id,
    validate_eth_address,
)


def get_epoch_blocks(chain_id: int, platform: str, epochs: List[int]):
    data_service = VoteMarketDataService(chain_id)
    rprint(Panel("Fetching Epoch Blocks", style="bold magenta"))

    blocks = data_service.get_epochs_block(chain_id, platform, epochs)

    os.makedirs("temp", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"temp/epoch_blocks_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(
            {
                "chain_id": chain_id,
                "platform": platform,
                "epochs": epochs,
                "blocks": blocks,
            },
            f,
            indent=2,
        )

    rprint("[cyan]Epoch Blocks:[/cyan]")
    for epoch, block in blocks.items():
        rprint(f"Epoch {epoch}: Block {block}")
    rprint(f"\n[cyan]Data saved to:[/cyan] {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Get epoch blocks for a platform"
    )
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

    except ValueError as e:
        rprint(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)
    except Exception as e:
        rprint(f"[red]Unexpected error:[/red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
