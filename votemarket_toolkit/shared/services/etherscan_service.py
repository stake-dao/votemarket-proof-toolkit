"""
Etherscan service module for interacting with the Etherscan API.

This module provides functions to fetch logs and token transfers from the Ethereum blockchain
using the Etherscan API. It includes rate limiting and error handling mechanisms.
"""

import logging
import os
import time
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

from votemarket_toolkit.shared.services.http_client import get_client

load_dotenv()

# Read once; validate lazily in call sites to avoid import-time failures
EXPLORER_KEY = os.getenv("EXPLORER_KEY")


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
    chain_id: str = "1",
) -> List[Dict[str, Any]]:
    """
    Get logs for a given address and topics from the specified explorer API.

    Args:
        address (str): Contract address to query logs for.
        from_block (int): Starting block number.
        to_block (int): Ending block number.
        topics (Dict[str, str]): Topics to filter logs.
        chain_id (str): Chain ID for the explorer (default: "1" for Ethereum mainnet).

    Returns:
        List[Dict[str, Any]]: List of logs.
    """
    topic0 = topics.get("0", "")
    offset = 1000
    page = 1
    all_logs = []

    while True:
        url = (
            f"https://api.etherscan.io/v2/api?"
            f"chainid={chain_id}&module=logs&action=getLogs&"
            f"address={address}&fromBlock={from_block}&toBlock={to_block}&"
            f"topic0={topic0}&page={page}&offset={offset}&apikey={EXPLORER_KEY}"
        )

        try:
            response = _make_request_with_retry(url, "logs")
            if not response:
                break

            all_logs.extend(response)

            # Stop if less than offset logs returned (meaning no more pages)
            if len(response) < offset:
                break

            page += 1  # Go to next page
        except Exception as e:
            if "No records found" in str(e):
                break
            raise

    return all_logs


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
    if not EXPLORER_KEY:
        raise ValueError(
            "EXPLORER_KEY is not set (required for Etherscan API calls)"
        )

    max_retries = 5
    client = get_client()
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.get(url)
            if response.status_code == 429:
                logging.info("Rate limit reached, retrying after delay...")
                delay(1000)
                continue

            data = response.json()

            if data.get("status") == "1":
                return data["result"]
            elif (
                data.get("status") == "0"
                and data.get("message") == f"No {request_type} found"
            ):
                logging.info(
                    f"No {request_type} found for the given parameters"
                )
                return {} if request_type == "logs" else []
            elif _is_rate_limit_error(data):
                logging.info("Rate limit reached, retrying after delay...")
                delay(1000)
            else:
                logging.error(f"Unexpected response: {data}")
                raise Exception(data.get("message") or "Unknown error")
        except httpx.RequestError as e:
            last_error = e
            logging.error(
                f"Error fetching {request_type} (attempt {attempt + 1}/{max_retries}): {str(e)}"
            )
            # Retry on network errors with exponential backoff
            if attempt < max_retries - 1:
                backoff_delay = 1000 * (2**attempt)  # 1s, 2s, 4s, 8s
                logging.info(f"Retrying after {backoff_delay}ms...")
                delay(backoff_delay)
                continue
            raise e


    if last_error:
        raise last_error
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
        or data["result"] == "Max calls per sec rate limit reached (3/sec)"
    )


def get_token_transfers(
    address: str,
    contract_address: str = None,
    from_block: int = 0,
    to_block: int = 99999999,
    sort: str = "asc",
    chain_id: str = "1",
) -> List[Dict[str, Any]]:
    """
    Get token transfers for a given address from the specified explorer API.

    Args:
        address (str): Ethereum address to query transfers for.
        contract_address (str, optional): Specific token contract address. Defaults to None.
        from_block (int, optional): Starting block number. Defaults to 0.
        to_block (int, optional): Ending block number. Defaults to 99999999.
        sort (str, optional): Sort order ('asc' or 'desc'). Defaults to 'asc'.
        chain_id (str): Chain ID for the explorer (default: "1" for Ethereum mainnet).

    Returns:
        List[Dict[str, Any]]: List of token transfers.

    Raises:
        Exception: If max retries are reached or an unexpected error occurs.
    """
    url = f"https://api.etherscan.io/v2/api?chainid={chain_id}&module=account&action=tokentx&address={address}&startblock={from_block}&endblock={to_block}&sort={sort}&apikey={EXPLORER_KEY}"

    if contract_address:
        url += f"&contractaddress={contract_address}"

    return _make_request_with_retry(url, "transfers")


def get_token_holders(contract_address: str, chain_id: str = "1") -> int:
    """
    Get the number of token holders for a given ERC20 token contract address.

    Args:
        contract_address (str): The contract address of the ERC20 token.
        chain_id (str): Chain ID for the explorer (default: "1" for Ethereum mainnet).

    Returns:
        int: The number of token holders.

    Raises:
        Exception: If max retries are reached or an unexpected error occurs.
    """
    url = f"https://api.etherscan.io/v2/api?chainid={chain_id}&module=stats&action=tokensupply&contractaddress={contract_address}&apikey={EXPLORER_KEY}"

    try:
        response = _make_request_with_retry(url, "token holders")
        return int(response)
    except ValueError:
        logging.error(f"Invalid response format for token holders: {response}")
        raise
    except Exception as e:
        logging.error(f"Error fetching token holders: {str(e)}")
        raise
