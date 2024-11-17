import json
import os
import sys

from rich import print as rprint
from rich.panel import Panel

from votemarket_toolkit.commands.validation import (
    validate_eth_address,
    validate_protocol,
)
from votemarket_toolkit.proofs.manager import VoteMarketProofs


def generate_gauge_proof(protocol, gauge_address, current_epoch, block_number):
    vm = VoteMarketProofs(1)
    rprint(Panel("Generating Gauge Proof", style="bold magenta"))

    gauge_proof = vm.get_gauge_proof(
        protocol, gauge_address, current_epoch, block_number
    )

    os.makedirs("temp", exist_ok=True)
    output_file = f"temp/gauge_proof_{block_number}.json"

    with open(output_file, "w") as f:
        json.dump(
            {
                "protocol": protocol,
                "gauge_address": gauge_address,
                "current_epoch": current_epoch,
                "block_number": block_number,
                "gauge_controller_proof": "0x"
                + gauge_proof["gauge_controller_proof"].hex(),
                "point_data_proof": "0x"
                + gauge_proof["point_data_proof"].hex(),
            },
            f,
            indent=2,
        )

    rprint("[cyan]Gauges Proofs saved to:[/cyan] " + output_file)
    rprint("[cyan]Gauge Controller Proof:[/cyan]")
    rprint(
        f'[green]0x{gauge_proof["gauge_controller_proof"].hex()[:50]}...[/green]'
    )
    rprint("[cyan]Point Data Proof:[/cyan]")
    rprint(f'[green]0x{gauge_proof["point_data_proof"].hex()[:50]}...[/green]')


def show_usage():
    rprint("[red]Error:[/red] Missing or invalid arguments")
    rprint("\n[cyan]Required arguments:[/cyan]")
    rprint("- PROTOCOL: Protocol name (curve, balancer)")
    rprint("- GAUGE_ADDRESS: Valid Ethereum address of the gauge")
    rprint("- CURRENT_EPOCH: Current epoch number (positive integer)")
    rprint("- BLOCK_NUMBER: Block number (positive integer)")
    rprint("\n[cyan]Example usage:[/cyan]")
    rprint("make gauge-proof \\")
    rprint("    PROTOCOL=curve \\")
    rprint("    GAUGE_ADDRESS=0x26f7786de3e6d9bd37fcf47be6f2bc455a21b74a \\")
    rprint("    CURRENT_EPOCH=1731542400 \\")
    rprint("    BLOCK_NUMBER=21185919")


def main():
    if len(sys.argv) != 5:
        show_usage()
        sys.exit(1)

    try:
        # Validate protocol
        protocol = validate_protocol(sys.argv[1])

        # Validate gauge address
        gauge_address = validate_eth_address(sys.argv[2], "gauge_address")

        # Validate numeric inputs
        current_epoch = int(sys.argv[3])
        block_number = int(sys.argv[4])

        if current_epoch <= 0 or block_number <= 0:
            raise ValueError(
                "CURRENT_EPOCH and BLOCK_NUMBER must be positive integers"
            )

        generate_gauge_proof(
            protocol, gauge_address, current_epoch, block_number
        )

    except ValueError as e:
        rprint(f"[red]Error:[/red] {str(e)}")
        show_usage()
        sys.exit(1)
    except Exception as e:
        rprint(f"[red]Unexpected error:[/red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
