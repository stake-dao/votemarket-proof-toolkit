from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

EXAMPLES = {
    "create_campaign_l1": "Create campaign from L1 (Ethereum → L2) with USDC rewards",
    "create_campaign_l2": "Create campaign on L2 with native USDC rewards",
    "manage_campaign_l1": "Add rewards to existing campaign from L1",
    "manage_campaign_l2": "Manage campaign directly on L2",
    "claim_rewards": "Process claims and submit required proofs",
}


def show_help(example: Optional[str] = None):
    console = Console()

    if example:
        if example not in EXAMPLES:
            console.print(f"[red]Error:[/red] Example '{example}' not found")
            console.print("\nAvailable examples:")
            for name, desc in EXAMPLES.items():
                console.print(f"  [cyan]{name}[/cyan]: {desc}")
            return

        # Show specific example help
        help_text = f"""# {example}

{EXAMPLES[example]}

## Usage
```bash
make run-example EXAMPLE={example}
```
"""
        md = Markdown(help_text)
        console.print(
            Panel.fit(
                md,
                title=f"{example} Help",
                border_style="cyan",
                padding=(1, 2),
            )
        )
    else:
        # Show general help
        help_text = """# VoteMarket Proofs Generator

This toolkit facilitates the generation of proofs and interaction with VoteMarketV2.

## Available Commands

### Setup & Maintenance
* `make install-dev`: Install development dependencies
* `make clean`: Remove virtual environment and cached files
* `make format`: Format code using black and ruff
* `make check`: Run code checks

### Proof Generation
* `make user-proof`: Generate a user proof
  Required: PROTOCOL, GAUGE_ADDRESS, USER_ADDRESS, BLOCK_NUMBER
  
* `make gauge-proof`: Generate a gauge proof
  Required: PROTOCOL, GAUGE_ADDRESS, CURRENT_EPOCH, BLOCK_NUMBER

### Information Retrieval
* `make block-info`: Get block information
  Required: BLOCK_NUMBER
  
* `make get-active-campaigns`: Get active campaigns
  Optional: CHAIN_ID, PLATFORM, PROTOCOL
  
* `make get-epoch-blocks`: Get set blocks for epochs
  Required: CHAIN_ID, PLATFORM, EPOCHS

### Examples
* `make run-example EXAMPLE=<name>`: Run specific example

Available examples:
"""
        # Add examples list to help text
        help_text += "\n".join(
            f"* `{name}`: {desc}" for name, desc in EXAMPLES.items()
        )

        help_text += """

## Example Usage:
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
