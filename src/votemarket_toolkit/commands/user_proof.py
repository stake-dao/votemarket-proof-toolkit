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


if __name__ == "__main__":
    protocol = sys.argv[1]
    gauge_address = sys.argv[2]
    user_address = sys.argv[3]
    block_number = int(sys.argv[4])
    generate_user_proof(protocol, gauge_address, user_address, block_number)
