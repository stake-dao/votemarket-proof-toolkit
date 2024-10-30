"""Example of how to generate proofs for a user and gauge."""

import os
from dotenv import load_dotenv
from proofs.main import VoteMarketProofs
from shared.constants import GlobalConstants
from shared.types import UserProof, GaugeProof, BlockInfo
from eth_utils import to_checksum_address
from rich import print as rprint
from rich.panel import Panel
from rich.console import Console

load_dotenv()

vm_proofs = VoteMarketProofs(1)
console = Console()

# Example parameters
PROTOCOL = "curve"
GAUGE_ADDRESS = to_checksum_address(
    "0x059e0db6bf882f5fe680dc5409c7adeb99753736".lower()
)
USER = to_checksum_address(
    "0xa219712cc2aaa5aa98ccf2a7ba055231f1752323".lower()
)
CURRENT_EPOCH = 1723680000
BLOCK_NUMBER = 20530737


def main():
    """Generate proofs for gauge (account + storage) and user (storage only needed)"""
    rprint(Panel("Starting VoteMarket Proof Generation", style="bold green"))

    # Get user proof
    rprint(Panel("Generating User Proof", style="bold magenta"))
    user_proof: UserProof = vm_proofs.get_user_proof(
        protocol=PROTOCOL,
        gauge_address=GAUGE_ADDRESS,
        user=USER,
        block_number=BLOCK_NUMBER,
    )
    rprint("[green]User proof generated successfully[/green]")

    # Get gauge proof
    rprint(Panel("Generating Gauge Proof", style="bold magenta"))
    gauge_proof: GaugeProof = vm_proofs.get_gauge_proof(
        protocol=PROTOCOL,
        gauge_address=GAUGE_ADDRESS,
        current_epoch=CURRENT_EPOCH,
        block_number=BLOCK_NUMBER,
    )
    rprint("[green]Gauge proof generated successfully[/green]")

    # Get block info
    rprint(Panel("Fetching Block Info", style="bold magenta"))
    block_info: BlockInfo = vm_proofs.get_block_info(BLOCK_NUMBER)
    rprint("[green]Block info fetched successfully[/green]")

    # Display results
    console.print("\n[cyan]Block Info:[/cyan]")
    console.print(f"Block Number: {block_info['block_number']}")
    console.print(f"Block Hash: {block_info['block_hash']}")
    console.print(f"Block Timestamp: {block_info['block_timestamp']}")
    console.print(
        f"RLP Block Header: {block_info['rlp_block_header'][:64]}..."
    )

    console.print("\n[cyan]Proof for Block (Gauge Controller):[/cyan]")
    console.print(f"0x{gauge_proof['gauge_controller_proof'].hex()[:64]}...")

    console.print("\n[cyan]Proof for Gauge (Point):[/cyan]")
    console.print(f"0x{gauge_proof['point_data_proof'].hex()[:64]}...")

    console.print("\n[cyan]User Proof (Account Data):[/cyan]")
    console.print(f"0x{user_proof['storage_proof'].hex()[:64]}...")

    rprint(Panel("VoteMarket Proof Generation Completed", style="bold green"))


if __name__ == "__main__":
    main()
