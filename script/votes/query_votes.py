import json
import os
from typing import List, Dict, Any
from web3 import Web3
from shared.constants import GaugeControllerConstants
from shared.etherscan_service import get_logs_by_address_and_topics
import logging
import asyncio

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

CACHE_DIR = "cache"
VOTES_CACHE_FILE = os.path.join(CACHE_DIR, "{protocol}_votes_cache.json")


async def query_gauge_votes(
    w3: Web3, protocol: str, gauge_address: str, block_number: int
) -> List[Dict[str, Any]]:
    cache_file = VOTES_CACHE_FILE.format(protocol=protocol)
    cached_data = load_cached_data(cache_file)

    start_block = cached_data.get(
        "latest_block", GaugeControllerConstants.CREATION_BLOCKS[protocol]
    )
    end_block = block_number

    if start_block < end_block:
        new_votes = await fetch_new_votes(w3, protocol, start_block, end_block)
        all_votes = cached_data.get("votes", []) + new_votes
        save_cached_data(cache_file, {"latest_block": end_block, "votes": all_votes})
    else:
        all_votes = cached_data.get("votes", [])

    # Filter votes for the specific gauge address
    filtered_votes = [vote for vote in all_votes if vote["gauge_addr"].lower() == gauge_address.lower()]

    return filtered_votes


async def fetch_new_votes(
    w3: Web3, protocol: str, start_block: int, end_block: int
) -> List[Dict[str, Any]]:
    INCREMENT = 100_000
    tasks = []

    for block in range(start_block, end_block + 1, INCREMENT):
        current_end_block = min(block + INCREMENT - 1, end_block)
        task = asyncio.create_task(
            fetch_votes_chunk(w3, protocol, block, current_end_block)
        )
        tasks.append(task)

    chunks = await asyncio.gather(*tasks)
    return [vote for chunk in chunks for vote in chunk]


async def fetch_votes_chunk(
    w3: Web3, protocol: str, start_block: int, end_block: int
) -> List[Dict[str, Any]]:
    logging.info(f"Getting logs from {start_block} to {end_block}")
    votes_logs = get_logs_by_address_and_topics(
        GaugeControllerConstants.GAUGE_CONTROLLER[protocol],
        start_block,
        end_block,
        {"0": GaugeControllerConstants.VOTE_EVENT_HASH},
    )

    logging.info(f"{len(votes_logs)} votes logs found")
    return [_decode_vote_log(log) for log in votes_logs]


def load_cached_data(cache_file: str) -> Dict[str, Any]:
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)
    return {}


def save_cached_data(cache_file: str, data: Dict[str, Any]):
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(data, f)


def _decode_vote_log(log: Dict[str, Any]) -> Dict[str, Any]:
    data = bytes.fromhex(log["data"][2:])  # Remove '0x' prefix and convert to bytes
    try:
        return {
            "time": int.from_bytes(data[0:32], byteorder="big"),
            "user": Web3.to_checksum_address("0x" + data[44:64].hex()),
            "gauge_addr": Web3.to_checksum_address("0x" + data[76:96].hex()),
            "weight": int.from_bytes(data[96:128], byteorder="big"),
        }
    except ValueError as e:
        raise ValueError(f"Error decoding vote log: {str(e)}. Raw data: {log['data']}")
