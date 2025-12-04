from typing import Any, Dict

import httpx

from votemarket_toolkit.shared.exceptions import APIException
from votemarket_toolkit.shared.services.http_client import get_client


def get_closest_block_timestamp(chain: str, timestamp: int) -> int:
    """Get the closest block number for a given timestamp using DefiLlama API"""
    url = f"https://coins.llama.fi/block/{chain}/{timestamp}"

    client = get_client()
    try:
        response = client.get(url)
    except httpx.RequestError as e:
        raise APIException(f"Failed to reach DefiLlama: {e}")

    if response.status_code != 200:
        raise APIException(
            f"Failed to get closest block timestamp: {response.text}"
        )


    result: Dict[str, Any] = response.json()
    return result["height"]
