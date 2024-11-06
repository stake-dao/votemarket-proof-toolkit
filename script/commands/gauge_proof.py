import json
import os
import sys

from proofs.main import VoteMarketProofs
from rich import print as rprint
from rich.panel import Panel


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


if __name__ == "__main__":
    protocol = sys.argv[1]
    gauge_address = sys.argv[2]
    current_epoch = int(sys.argv[3])
    block_number = int(sys.argv[4])
    generate_gauge_proof(protocol, gauge_address, current_epoch, block_number)
