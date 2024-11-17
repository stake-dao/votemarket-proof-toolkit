import json
import os
import sys

from rich import print as rprint
from rich.panel import Panel

from votemarket_toolkit.proofs import VoteMarketProofs


def generate_user_proof(protocol, gauge_address, user_address, block_number):
    vm = VoteMarketProofs(1)
    rprint(Panel("Generating User Proof", style="bold magenta"))

    user_proof = vm.get_user_proof(
        protocol, gauge_address, user_address, block_number
    )

    os.makedirs("temp", exist_ok=True)
    output_file = f"temp/user_proof_{block_number}.json"

    with open(output_file, "w") as f:
        json.dump(
            {
                "protocol": protocol,
                "gauge_address": gauge_address,
                "user_address": user_address,
                "block_number": block_number,
                "storage_proof": "0x" + user_proof["storage_proof"].hex(),
            },
            f,
            indent=2,
        )

    rprint("[cyan]User Proof saved to:[/cyan] " + output_file)
    rprint("[cyan]User Proof:[/cyan]")
    rprint(f'[green]0x{user_proof["storage_proof"].hex()[:50]}...[/green]')


def main():
    # Check if any arguments were provided
    if len(sys.argv) == 1:
        rprint("[red]Error:[/red] No arguments provided")
        show_usage()
        sys.exit(1)

    if len(sys.argv) != 5:
        rprint("[red]Error:[/red] Missing required arguments")
        show_usage()
        sys.exit(1)

    # Check for empty arguments
    if not all(sys.argv[1:]):
        rprint("[red]Error:[/red] All arguments must be provided")
        show_usage()
        sys.exit(1)

    try:
        protocol = sys.argv[1].lower()  # Convert to lowercase
        gauge_address = sys.argv[2]
        user_address = sys.argv[3]
        block_number = int(sys.argv[4])

        # Basic address validation
        if not gauge_address.startswith("0x") or len(gauge_address) != 42:
            raise ValueError("Invalid gauge address format")
        if not user_address.startswith("0x") or len(user_address) != 42:
            raise ValueError("Invalid user address format")

        generate_user_proof(
            protocol, gauge_address, user_address, block_number
        )

    except ValueError as e:
        rprint(f"[red]Error:[/red] {str(e)}")
        show_usage()
        sys.exit(1)


def show_usage():
    rprint("\n[cyan]Required arguments:[/cyan]")
    rprint("- PROTOCOL: Protocol name (e.g., curve, balancer)")
    rprint("- GAUGE_ADDRESS: Address of the gauge")
    rprint("- USER_ADDRESS: Address of the user")
    rprint("- BLOCK_NUMBER: Block number")
    rprint("\n[cyan]Example usage:[/cyan]")
    rprint("make user-proof \\")
    rprint("    PROTOCOL=curve \\")
    rprint("    GAUGE_ADDRESS=0x26f7786de3e6d9bd37fcf47be6f2bc455a21b74a \\")
    rprint("    USER_ADDRESS=0x52f541764e6e90eebc5c21ff570de0e2d63766b6 \\")
    rprint("    BLOCK_NUMBER=21185919")


if __name__ == "__main__":
    main()
