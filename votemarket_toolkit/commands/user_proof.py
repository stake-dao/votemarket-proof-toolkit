import argparse

from rich.panel import Panel

from votemarket_toolkit.commands.helpers import handle_command_error
from votemarket_toolkit.commands.validation import (
    validate_eth_address,
    validate_protocol,
)
from votemarket_toolkit.proofs import VoteMarketProofs
from votemarket_toolkit.utils.formatters import console, save_json_output


def generate_user_proof(protocol, gauge_address, user_address, block_number):
    vm = VoteMarketProofs(1)
    console.print(Panel("Generating User Proof", style="bold magenta"))

    user_proof = vm.get_user_proof(
        protocol, gauge_address, user_address, block_number
    )

    output_data = {
        "protocol": protocol,
        "gauge_address": gauge_address,
        "user_address": user_address,
        "block_number": block_number,
        "storage_proof": "0x" + user_proof["storage_proof"].hex(),
    }

    filename = f"user_proof_{block_number}.json"
    save_json_output(output_data, filename)

    console.print("[cyan]User Proof:[/cyan]")
    console.print(
        f'[green]0x{user_proof["storage_proof"].hex()[:50]}...[/green]'
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate user proof for a gauge"
    )
    parser.add_argument(
        "--protocol",
        type=str,
        required=True,
        help="Protocol name (e.g., curve, balancer)",
    )
    parser.add_argument(
        "--gauge-address",
        type=str,
        required=True,
        help="Address of the gauge",
    )
    parser.add_argument(
        "--user-address",
        type=str,
        required=True,
        help="Address of the user",
    )
    parser.add_argument(
        "--block-number",
        type=int,
        required=True,
        help="Block number",
    )

    args = parser.parse_args()

    try:
        # Validate protocol
        protocol = validate_protocol(args.protocol)

        # Validate addresses
        gauge_address = validate_eth_address(
            args.gauge_address, "gauge_address"
        )
        user_address = validate_eth_address(args.user_address, "user_address")

        # Validate block number
        if args.block_number <= 0:
            raise ValueError("Block number must be a positive integer")

        generate_user_proof(
            protocol, gauge_address, user_address, args.block_number
        )

    except (ValueError, Exception) as e:
        handle_command_error(e)


if __name__ == "__main__":
    main()
