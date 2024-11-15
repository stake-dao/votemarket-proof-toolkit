from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

help_text = """# VoteMarket Proofs Generator

This Makefile facilitates the generation of RLP-encoded proofs for VoteMarketV2.

## Available targets:
* **all**: Set up the virtual environment and install dependencies
* **install**: Same as 'all'
* **clean**: Remove virtual environment and cached Python files
* **test**: Run tests
* **integration**: Run integration tests
* **user-proof**: Generate a user proof
* **gauge-proof**: Generate a gauge proof
* **block-info**: Get block information
* **get-active-campaigns**: Get active campaigns
* **get-epoch-blocks**: Get set blocks for epochs

## Example usage:
```bash
# Generate user proof
make user-proof \\
    PROTOCOL=curve \\
    GAUGE_ADDRESS=0x... \\
    USER=0x... \\
    BLOCK_NUMBER=12345678

# Get epoch blocks
make get-epoch-blocks \\
    CHAIN_ID=1 \\
    PLATFORM=0x... \\
    EPOCHS=1234,1235,1236
```
"""


def show_help():
    console = Console()
    md = Markdown(help_text)
    console.print(
        Panel.fit(
            md,
            title="VoteMarket Proofs Help",
            border_style="cyan",
            padding=(1, 2),
        )
    )


if __name__ == "__main__":
    show_help()
