import json
import os
import argparse
from typing import List, Dict

from dotenv import load_dotenv
from votes.query_campaigns import get_all_platforms

load_dotenv()

TEMP_DIR = "temp"

def process_protocol(protocol: str) -> Dict[str, List[Dict[str, str]]]:
    # Get all platforms for the protocol
    platforms = get_all_platforms(protocol)

    return {
        "protocol": protocol,
        "platforms": platforms
    }

def main(protocols: List[str]):
    all_protocols_data = []

    for protocol in protocols:
        protocol_data = process_protocol(protocol)
        all_protocols_data.append(protocol_data)

    json_data = {
        "protocols": all_protocols_data
    }

    # Store in a json file
    os.makedirs(TEMP_DIR, exist_ok=True)
    output_file = f"{TEMP_DIR}/all_platforms.json"
    with open(output_file, "w") as f:
        json.dump(json_data, f, indent=2)

    print(f"Saved data for all protocols to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a list of all platforms for given protocols")
    parser.add_argument(
        "protocols",
        type=str,
        nargs="+",
        help="List of protocol names (e.g., 'curve', 'balancer')",
    )

    args = parser.parse_args()

    main(args.protocols)