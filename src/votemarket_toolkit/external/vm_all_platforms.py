"""
This script generates a JSON file containing information about all platforms
for specified protocols. It's designed to be used in conjunction with
vm_active_proofs.py as part of the automated process of generating proofs.

The script fetches data for each protocol and platform, including:
- Platform addresses
- Latest setted block numbers (on Oracle)
- Block data for the latest setted blocks

The resulting JSON file serves as input for subsequent proof generation steps.
"""

import argparse
import asyncio
import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from eth_utils import to_checksum_address
from rich import print as rprint

from votemarket_toolkit.campaigns.services.campaign_service import (
    CampaignService,
)
from votemarket_toolkit.proofs.manager import VoteMarketProofs
from votemarket_toolkit.shared.constants import GlobalConstants
from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.shared.types import AllProtocolsData, ProtocolData
from votemarket_toolkit.utils.blockchain import get_rounded_epoch

load_dotenv()

TEMP_DIR = "temp"

campaign_service = CampaignService()


def get_block_data(block_number: int) -> Dict[str, Any]:
    """
    Retrieve block data for a given block number.

    Args:
        block_number (int): The block number to fetch data for.

    Returns:
        Dict[str, Any]: A dictionary containing block data.
    """
    vm_proofs = VoteMarketProofs(1)
    block_info = vm_proofs.get_block_info(block_number)
    return {
        "block_number": block_info["block_number"],
        "block_hash": block_info["block_hash"],
        "block_timestamp": block_info["block_timestamp"],
        "rlp_block_header": block_info["rlp_block_header"],
    }


async def process_protocol(
    protocol: str, epoch: int, block: int = None
) -> ProtocolData:
    """
    Process a single protocol to gather platform information.

    Args:
        protocol (str): The name of the protocol to process.
        epoch (int): The epoch to use for fetching data.
        block (int, optional): Specific block number to use. If None, uses latest setted block from oracle.

    Returns:
        ProtocolData: A dictionary containing the protocol name and a list of platform data.
    """
    # Always treat epoch as rounded
    epoch = get_rounded_epoch(epoch)

    rprint(f"Processing protocol: [blue]{protocol}[/blue]")
    platforms = campaign_service.get_all_platforms(protocol)
    rprint(
        f"Found [green]{len(platforms)}[/green] platforms for"
        f" [blue]{protocol}[/blue]"
    )

    protocol_data: ProtocolData = {"platforms": {}}

    for platform in platforms:
        chain_id = platform["chain_id"]
        platform_address = platform["address"]

        rprint(f"Processing platform: {platform_address} on chain {chain_id}")

        # Get Web3Service instance for this chain
        web3_service = Web3Service.get_instance(chain_id)

        platform_contract = web3_service.get_contract(
            platform_address, "vm_platform"
        )
        lens = platform_contract.functions.ORACLE().call()
        lens_address = to_checksum_address(lens.lower())

        lens_contract = web3_service.get_contract(lens_address, "oracle_lens")
        oracle_address = lens_contract.functions.oracle().call()
        oracle_address = to_checksum_address(oracle_address.lower())

        if oracle_address == "0x0000000000000000000000000000000000000000":
            rprint(
                f"Skipping platform {platform_address} on chain {chain_id} as"
                " it doesn't have an oracle"
            )
            continue

        oracle = web3_service.get_contract(oracle_address, "oracle")
        latest_setted_block = (
            block
            if block is not None
            else oracle.functions.epochBlockNumber(epoch).call()[2]
        )

        block_data = get_block_data(latest_setted_block)
        timestamp = block_data["block_timestamp"]
        block_period_timestamp = (
            timestamp // GlobalConstants.WEEK
        ) * GlobalConstants.WEEK

        if block_period_timestamp < epoch:
            rprint(
                "[italic red]Latest setted block timestamp[/italic red]"
                f" ({block_period_timestamp}) [italic red]is less than current"
                f" period timestamp[/italic red] ({epoch}) [italic red]for"
                f" platform[/italic red] {platform_address} [italic red]on"
                f" chain[/italic red] {chain_id}. [italic"
                " red]Skipping.[/italic red]"
            )
            continue

        # Store platform data according to type structure
        protocol_data["platforms"][chain_id] = {
            "address": platform_address,
            "latest_setted_block": latest_setted_block,
            "block_data": block_data,
            "oracle_address": oracle_address,
            "lens_address": lens_address,
        }

    return protocol_data


async def main(
    protocols: List[str], epoch: int, block: int = None
) -> AllProtocolsData:
    """
    Process all specified protocols and generate the JSON output.

    Args:
        protocols (List[str]): List of protocol names to process.
        epoch (int): The epoch to use for fetching data.
        block (int, optional): Specific block number to use. If None, uses latest setted block from oracle.

    Returns:
        AllProtocolsData: A dictionary containing data for all processed protocols.
    """
    all_protocols_data: AllProtocolsData = {"protocols": {}}

    for protocol in protocols:
        protocol_data = await process_protocol(protocol, epoch, block)
        all_protocols_data["protocols"][protocol] = protocol_data

    os.makedirs(TEMP_DIR, exist_ok=True)
    output_file = f"{TEMP_DIR}/all_platforms.json"
    with open(output_file, "w") as f:
        json.dump(all_protocols_data, f, indent=2)

    rprint(f"Saved data for all protocols to {output_file}")
    return all_protocols_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a list of all platforms for given protocols"
    )
    parser.add_argument(
        "protocols",
        type=str,
        nargs="+",
        help="List of protocol names (e.g., 'curve', 'balancer')",
    )
    parser.add_argument(
        "--epoch",
        type=int,
        required=True,
        help="epoch to use for fetching latest block on the ORACLE",
    )
    parser.add_argument(
        "--block",
        type=int,
        required=False,
        help=(
            "Specific block number to use (optional). If not provided, uses"
            " latest setted block from oracle."
        ),
    )

    args = parser.parse_args()
    asyncio.run(main(args.protocols, args.epoch, args.block))
