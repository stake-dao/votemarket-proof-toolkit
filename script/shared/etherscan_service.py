"""
Etherscan service module for interacting with the Etherscan API.

This module provides functions to fetch logs and token transfers from the Ethereum blockchain
using the Etherscan API. It includes rate limiting and error handling mechanisms.
"""

import os
import time
import logging
from typing import Dict, List, Any
import requests
from dotenv import load_dotenv

load_dotenv()

ETHERSCAN_KEY = os.getenv("ETHERSCAN_TOKEN", "")


class RateLimiter:
    """
    A simple rate limiter to control concurrent API requests.

    Attributes:
        max_concurrent (int): Maximum number of concurrent requests allowed.
        queue (list): Queue of pending requests.
        running (int): Number of currently running requests.
    """

    def __init__(self, max_concurrent: int):
        self.max_concurrent = max_concurrent
        self.queue = []
        self.running = 0

    def add(self, fn):
        """
        Add a function to be executed under rate limiting.

        Args:
            fn (callable): Function to be executed.

        Returns:
            Any: Result of the executed function.
        """
        while self.running >= self.max_concurrent:
            time.sleep(0.1)
        self.running += 1
        try:
            return fn()
        finally:
            self.running -= 1
            if self.queue:
                self.queue.pop(0)()


rate_limiter = RateLimiter(5)


def delay(ms: int):
    """
    Introduce a delay in milliseconds.

    Args:
        ms (int): Delay in milliseconds.
    """
    time.sleep(ms / 1000)


def get_logs_by_address_and_topics(
    address: str,
    from_block: int,
    to_block: int,
    topics: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Get logs for a given address and topics from the Etherscan API.

    Args:
        address (str): Contract address to query logs for.
        from_block (int): Starting block number.
        to_block (int): Ending block number.
        topics (Dict[str, str]): Topics to filter logs.

    Returns:
        List[Dict[str, Any]]: List of logs.
    """
    topic0 = topics.get("0", "")
    url = f"https://api.etherscan.io/api?module=logs&action=getLogs&address={address}&fromBlock={from_block}&toBlock={to_block}&topic0={topic0}&apikey={ETHERSCAN_KEY}"

    try:
        response = _make_request_with_retry(url, "logs")
        return response if response else []
    except Exception as e:
        if "No records found" in str(e):
            return []
        raise


def _make_request_with_retry(url: str, request_type: str) -> Dict[str, Any]:
    """
    Make an API request with retry logic.

    Args:
        url (str): API endpoint URL.
        request_type (str): Type of request (e.g., "logs", "transfers").

    Returns:
        Dict[str, Any]: API response data.

    Raises:
        Exception: If max retries are reached or an unexpected error occurs.
    """
    max_retries = 5
    for _ in range(max_retries):
        try:
            response = requests.get(url)
            data = response.json()

            if data["status"] == "1":
                return data["result"]
            elif (
                data["status"] == "0" and data["message"] == f"No {request_type} found"
            ):
                logging.info(f"No {request_type} found for the given parameters")
                return {} if request_type == "logs" else []
            elif _is_rate_limit_error(data):
                logging.info("Rate limit reached, retrying after delay...")
                delay(1000)
            else:
                logging.error(f"Unexpected response: {data}")
                raise Exception(data["message"] or "Unknown error")
        except requests.RequestException as e:
            if response.status_code == 429:
                logging.info("Rate limit reached, retrying after delay...")
                delay(1000)
            else:
                logging.error(f"Error fetching {request_type}: {str(e)}")
                raise e

    raise Exception("Max retries reached")


def _is_rate_limit_error(data: Dict[str, Any]) -> bool:
    """
    Check if the API response indicates a rate limit error.

    Args:
        data (Dict[str, Any]): API response data.

    Returns:
        bool: True if it's a rate limit error, False otherwise.
    """
    return data["message"] == "NOTOK" and (
        data["result"] == "Max rate limit reached"
        or data["result"] == "Max calls per sec rate limit reached (5/sec)"
    )


def get_token_transfers(
    address: str,
    contract_address: str = None,
    from_block: int = 0,
    to_block: int = 99999999,
    sort: str = "asc",
) -> List[Dict[str, Any]]:
    """
    Get token transfers for a given address from the Etherscan API.

    Args:
        address (str): Ethereum address to query transfers for.
        contract_address (str, optional): Specific token contract address. Defaults to None.
        from_block (int, optional): Starting block number. Defaults to 0.
        to_block (int, optional): Ending block number. Defaults to 99999999.
        sort (str, optional): Sort order ('asc' or 'desc'). Defaults to 'asc'.

    Returns:
        List[Dict[str, Any]]: List of token transfers.

    Raises:
        Exception: If max retries are reached or an unexpected error occurs.
    """
    url = f"https://api.etherscan.io/api?module=account&action=tokentx&address={address}&startblock={from_block}&endblock={to_block}&sort={sort}&apikey={ETHERSCAN_KEY}"

    if contract_address:
        url += f"&contractaddress={contract_address}"

    return _make_request_with_retry(url, "transfers")
