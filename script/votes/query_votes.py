import logging
from typing import List, Dict, Any
from web3 import Web3
from shared.constants import GaugeControllerConstants
from shared.etherscan_service import get_logs_by_address_and_topics
from shared.parquet_cache_service import ParquetCache
import logging
import asyncio

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

CACHE_DIR = "cache"
VOTES_CACHE_FILE = "{protocol}_votes_cache.parquet"

cache = ParquetCache(CACHE_DIR)


async def query_gauge_votes(
    w3: Web3, protocol: str, gauge_address: str, block_number: int
) -> List[Dict[str, Any]]:
    """
    Query gauge votes from gauge controller contract and cache.

    Args:
        w3 (Web3): Web3 instance.
        protocol (str): Protocol name.
        gauge_address (str): Gauge address.
        block_number (int): Block number to query up to.

    Returns:
        List[Dict[str, Any]]: List of votes.
    """
    cache_file = VOTES_CACHE_FILE.format(protocol=protocol)
    start_block_list = cache.get_columns(cache_file, ["latest_block"]).get(
        "latest_block", []
    )
    start_block = (
        start_block_list[0]
        if start_block_list
        else GaugeControllerConstants.CREATION_BLOCKS[protocol]
    )

    end_block = block_number
    logging.info(f"Getting votes for {gauge_address} from {start_block} to {end_block}")

    if start_block < end_block:
        new_votes = await fetch_new_votes(w3, protocol, start_block, end_block)

        cached_data = cache.get_columns(
            cache_file, ["time", "user", "gauge_addr", "weight"]
        )
        cached_votes = [
            {"time": t, "user": u, "gauge_addr": g, "weight": w}
            for t, u, g, w in zip(
                cached_data["time"],
                cached_data["user"],
                cached_data["gauge_addr"],
                cached_data["weight"],
            )
        ]
        all_votes = cached_votes + new_votes
        print(f"All votes length: {len(all_votes)}")
        cache.save_votes(cache_file, end_block, all_votes)
    else:
        logging.info("Using cached data as start block is not less than end block")
        cached_data = cache.get_columns(
            cache_file, ["time", "user", "gauge_addr", "weight"]
        )
        all_votes = [
            {"time": t, "user": u, "gauge_addr": g, "weight": w}
            for t, u, g, w in zip(
                cached_data["time"],
                cached_data["user"],
                cached_data["gauge_addr"],
                cached_data["weight"],
            )
        ]

    # Filter votes for the specific gauge address
    filtered_votes = [
        vote
        for vote in all_votes
        if vote["gauge_addr"].lower() == gauge_address.lower()
    ]

    return filtered_votes


async def fetch_new_votes(
    w3: Web3, protocol: str, start_block: int, end_block: int
) -> List[Dict[str, Any]]:
    """
    Fetch new votes from gauge controller contract.

    Args:
        w3 (Web3): Web3 instance.
        protocol (str): Protocol name.
        start_block (int): Starting block number.
        end_block (int): Ending block number.

    Returns:
        List[Dict[str, Any]]: List of new votes.
    """
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
    """
    Fetch a chunk of votes from gauge controller contract.

    Args:
        w3 (Web3): Web3 instance.
        protocol (str): Protocol name.
        start_block (int): Starting block number.
        end_block (int): Ending block number.

    Returns:
        List[Dict[str, Any]]: List of votes in the chunk.
    """
    logging.info(f"Getting logs from {start_block} to {end_block}")
    try:
        votes_logs = get_logs_by_address_and_topics(
            GaugeControllerConstants.GAUGE_CONTROLLER[protocol],
            start_block,
            end_block,
            {"0": GaugeControllerConstants.VOTE_EVENT_HASH},
        )
        logging.info(f"{len(votes_logs)} votes logs found")
        return [_decode_vote_log(log) for log in votes_logs]
    except Exception as e:
        if "No records found" in str(e):
            logging.info(f"No votes found from {start_block} to {end_block}")
            return []
        else:
            raise  # Re-raise the exception if it's not a "No records found" error


def _decode_vote_log(log: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decode a vote log.

    Args:
        log (Dict[str, Any]): Log data.

    Returns:
        Dict[str, Any]: Decoded vote data.
    """
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
