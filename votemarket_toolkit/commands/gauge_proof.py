import argparse
import sys

from rich.panel import Panel

from votemarket_toolkit.commands.helpers import handle_command_error
from votemarket_toolkit.commands.validation import (
    validate_eth_address,
    validate_protocol,
)
from votemarket_toolkit.proofs.manager import VoteMarketProofs
from votemarket_toolkit.utils.formatters import console, save_json_output


def generate_gauge_proof(protocol, gauge_address, current_epoch, block_number):
    vm = VoteMarketProofs(1)
    console.print(Panel("Generating Gauge Proof", style="bold magenta"))

    gauge_proof = vm.get_gauge_proof(
        protocol, gauge_address, current_epoch, block_number
    )

    output_data = {
        "protocol": protocol,
        "gauge_address": gauge_address,
        "current_epoch": current_epoch,
        "block_number": block_number,
        "gauge_controller_proof": "0x" + gauge_proof["gauge_controller_proof"].hex(),
        "point_data_proof": "0x" + gauge_proof["point_data_proof"].hex(),
    }

    filename = f"gauge_proof_{block_number}.json"
    save_json_output(output_data, filename)

    console.print("[cyan]Gauge Controller Proof:[/cyan]")
    console.print(
        f'[green]0x{gauge_proof["gauge_controller_proof"].hex()[:50]}...[/green]'
    )
    console.print("[cyan]Point Data Proof:[/cyan]")
    console.print(f'[green]0x{gauge_proof["point_data_proof"].hex()[:50]}...[/green]')


def main():
    parser = argparse.ArgumentParser(description="Generate gauge proof")
    parser.add_argument(
        "--protocol",
        type=str,
        required=True,
        help="Protocol name (curve, balancer)",
    )
    parser.add_argument(
        "--gauge-address",
        type=str,
        required=True,
        help="Valid Ethereum address of the gauge",
    )
    parser.add_argument(
        "--current-epoch",
        type=int,
        required=True,
        help="Current epoch number (positive integer)",
    )
    parser.add_argument(
        "--block-number",
        type=int,
        required=True,
        help="Block number (positive integer)",
    )

    args = parser.parse_args()

    try:
        # Validate protocol
        protocol = validate_protocol(args.protocol)

        # Validate gauge address
        gauge_address = validate_eth_address(args.gauge_address, "gauge_address")

        # Validate numeric inputs
        if args.current_epoch <= 0 or args.block_number <= 0:
            raise ValueError(
                "CURRENT_EPOCH and BLOCK_NUMBER must be positive integers"
            )

        generate_gauge_proof(
            protocol, gauge_address, args.current_epoch, args.block_number
        )

    except (ValueError, Exception) as e:
        handle_command_error(e)


if __name__ == "__main__":
    main()
