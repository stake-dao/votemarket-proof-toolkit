from typing import Any, Dict

import requests

from votemarket_toolkit.shared.exceptions import APIException


def get_closest_block_timestamp(chain: str, timestamp: int) -> int:
    """Get the closest block number for a given timestamp using DefiLlama API"""
    url = f"https://coins.llama.fi/block/{chain}/{timestamp}"

    response = requests.get(url)
    if response.status_code != 200:
        raise APIException(
            f"Failed to get closest block timestamp: {response.text}"
        )

    result: Dict[str, Any] = response.json()
    return result["height"]
