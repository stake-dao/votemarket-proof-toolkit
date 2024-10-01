import json
import os
import argparse
from typing import List, Dict

from eth_utils import to_checksum_address
from dotenv import load_dotenv
from shared.constants import GlobalConstants
from shared.web3_service import Web3Service
from votes.query_campaigns import get_all_platforms

load_dotenv()

TEMP_DIR = "temp"

"""
This script generates a JSON file containing information about all platforms
for specified protocols. It's designed to be used in conjunction with
vm_active_proofs.py as part of the automated process of generating proofs.
"""

def process_protocol(protocol: str, period: int) -> Dict[str, List[Dict[str, str]]]:
    """
    Process a single protocol to gather platform information.

    Args:
        protocol (str): The name of the protocol to process.
        period (int): The period to use for fetching data.

    Returns:
        Dict[str, List[Dict[str, str]]]: A dictionary containing the protocol name and a list of platform data.
    """
    platforms = get_all_platforms(protocol)
    web3_service = Web3Service(1, GlobalConstants.CHAIN_ID_TO_RPC[1])

    for platform in platforms:
        chain_id = platform["chain_id"]
        platform_address = platform["platform"]
        """" TODO : Put back once prod ready
        if chain_id not in web3_service.w3:
            web3_service.add_chain(chain_id, GlobalConstants.CHAIN_ID_TO_RPC[chain_id])

        # Fetch the oracle address from platform
        platform_contract = web3_service.get_contract(platform_address, "vm_platform", chain_id)
        oracle_address = platform_contract.functions.ORACLE().call()
        oracle_address = to_checksum_address(oracle_address.lower())

        if oracle_address != "0x0000000000000000000000000000000000000000":
            oracle = web3_service.get_contract(oracle_address, "oracle", chain_id)
            latest_setted_block = oracle.functions.epochBlockNumber(period).call()
        else:
            latest_setted_block = web3_service.w3[chain_id].eth.get_block('latest')['number']

        platform['latest_setted_block'] = latest_setted_block
        """
        platform["latest_setted_block"] = 20873530

    return {"protocol": protocol, "platforms": platforms}


def main(protocols: List[str], period: int):
    all_protocols_data = []

    for protocol in protocols:
        protocol_data = process_protocol(protocol, period)
        all_protocols_data.append(protocol_data)

    json_data = {"protocols": all_protocols_data}

    os.makedirs(TEMP_DIR, exist_ok=True)
    output_file = f"{TEMP_DIR}/all_platforms.json"
    with open(output_file, "w") as f:
        json.dump(json_data, f, indent=2)

    print(f"Saved data for all protocols to {output_file}")


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
        "--period",
        type=int,
        required=True,
        help="Period to use for fetching data",
    )

    args = parser.parse_args()
    main(args.protocols, args.period)
