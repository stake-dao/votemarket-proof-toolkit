"""
Etherscan service module for interacting with the Etherscan API.

This module provides functions to fetch logs and token transfers from the Ethereum blockchain
using the Etherscan API. It uses the shared retry framework for error handling.
"""

import logging
import os
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

from votemarket_toolkit.shared.exceptions import APIException
from votemarket_toolkit.shared.retry import retry_sync_operation
from votemarket_toolkit.shared.services.http_client import get_client

load_dotenv()

# Read once; validate lazily in call sites to avoid import-time failures
EXPLORER_KEY = os.getenv("EXPLORER_KEY")

# Retryable exceptions for Etherscan API calls
ETHERSCAN_RETRYABLE_EXCEPTIONS = (
    APIException,
    httpx.RequestError,
    ConnectionError,
    TimeoutError,
)


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


def _do_single_request(url: str, request_type: str) -> Dict[str, Any]:
    """
    Make a single API request (no retry logic).

    Args:
        url (str): API endpoint URL.
        request_type (str): Type of request (e.g., "logs", "transfers").

    Returns:
        Dict[str, Any]: API response data.

    Raises:
        APIException: For rate limits and transient errors (will be retried).
        ValueError: For configuration errors (won't be retried).
        Exception: For permanent API errors (won't be retried).
    """
    if not EXPLORER_KEY:
        raise ValueError(
            "EXPLORER_KEY is not set (required for Etherscan API calls)"
        )

    client = get_client()
    response = client.get(url)

    # HTTP 429 rate limit
    if response.status_code == 429:
        raise APIException("Rate limit reached (HTTP 429)")

    data = response.json()

    # Success
    if data.get("status") == "1":
        return data["result"]

    # No records found - not an error
    if (
        data.get("status") == "0"
        and data.get("message") == f"No {request_type} found"
    ):
        logging.info(f"No {request_type} found for the given parameters")
        return {} if request_type == "logs" else []

    # API rate limit error
    if _is_rate_limit_error(data):
        raise APIException(f"Rate limit reached: {data.get('result')}")

    # Other API errors - not retryable
    logging.error(f"Unexpected response: {data}")
    raise Exception(data.get("message") or "Unknown error")


def _make_request_with_retry(url: str, request_type: str) -> Dict[str, Any]:
    """
    Make an API request with retry logic using shared retry framework.

    Args:
        url (str): API endpoint URL.
        request_type (str): Type of request (e.g., "logs", "transfers").

    Returns:
        Dict[str, Any]: API response data.

    Raises:
        Exception: If max retries are reached or an unexpected error occurs.
    """
    return retry_sync_operation(
        _do_single_request,
        url,
        request_type,
        max_attempts=5,
        base_delay=1.0,
        max_delay=8.0,
        exponential=True,
        retryable_exceptions=ETHERSCAN_RETRYABLE_EXCEPTIONS,
        operation_name=f"etherscan_{request_type}",
    )


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
