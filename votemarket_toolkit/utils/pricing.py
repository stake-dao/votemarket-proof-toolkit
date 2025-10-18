"""
Pricing utilities for fetching ERC20 token prices.
"""

import time
from typing import List, Optional, Tuple

import httpx
from eth_utils.address import to_checksum_address

try:
    from votemarket_toolkit.shared.constants import GlobalConstants
except ImportError:
    # Fallback if GlobalConstants is not available
    class GlobalConstants:
        chains_ids_to_name = {
            1: "ethereum",
            10: "optimism",
            137: "polygon",
            8453: "base",
            42161: "arbitrum",
        }


# Price cache to avoid repeated API calls
_price_cache = {}
_cache_ttl = 300  # 5 minutes TTL


def calculate_usd_per_vote(
    reward_per_vote: int, token_price_usd: float, token_decimals: int = 18
) -> float:
    """
    Calculate USD value per vote.

    Args:
        reward_per_vote: Reward per vote in token wei
        token_price_usd: Token price in USD
        token_decimals: Token decimals (default 18)

    Returns:
        USD value per vote
    """
    if reward_per_vote == 0 or token_price_usd == 0:
        return 0.0

    # Convert from wei to token amount
    token_amount = reward_per_vote / (10**token_decimals)

    # Calculate USD value
    return token_amount * token_price_usd


def format_usd_value(value: float, compact: bool = False) -> str:
    """
    Format USD value for display.

    Args:
        value: USD value
        compact: If True, use compact notation for large values

    Returns:
        Formatted string
    """
    if value == 0:
        return "$0"

    if compact and value >= 1000000:
        return f"${value/1000000:.2f}M"
    elif compact and value >= 1000:
        return f"${value/1000:.2f}K"
    elif value < 0.0001:
        return f"${value:.8f}"
    elif value < 0.01:
        return f"${value:.6f}"
    elif value < 1:
        return f"${value:.4f}"
    else:
        return f"${value:,.2f}"


def get_erc20_prices_in_usd(
    chain_id: int,
    token_amounts: List[Tuple[str, int]],
    timestamp: Optional[int] = None,
) -> List[Tuple[str, float]]:
    """
    Fetch prices for multiple tokens in a single API call to reduce rate limit issues.

    Args:
        chain_id: The chain ID
        token_amounts: List of tuples (token_address, unformatted_amount)
        timestamp: Optional timestamp for historical prices

    Returns:
        List of tuples (formatted_price_string, price_float)
    """
    if not token_amounts:
        return []

    network = GlobalConstants.chains_ids_to_name[chain_id]

    # Check cache first
    results = []
    uncached_tokens = []
    current_time = time.time()

    for token_address, unformatted_amount in token_amounts:
        cache_key = f"{network}:{to_checksum_address(token_address.lower())}:{timestamp or 'current'}"
        if cache_key in _price_cache:
            cached_data = _price_cache[cache_key]
            if isinstance(cached_data, tuple) and len(cached_data) >= 2:
                cached_price, cached_time = cached_data[0], cached_data[1]
                # Check if we also cached decimals (new format)
                cached_decimals = (
                    cached_data[2] if len(cached_data) > 2 else 18
                )

                if current_time - cached_time < _cache_ttl:
                    # Use cached price
                    if cached_price > 0:
                        amount = int(unformatted_amount)
                        price = cached_price * (amount / 10**cached_decimals)
                        results.append(("{:,.2f}".format(price), price))
                    else:
                        results.append(("0.00", 0))
                    continue

        uncached_tokens.append((token_address, unformatted_amount))
        results.append(None)  # Placeholder

    if not uncached_tokens:
        return results

    # Build comma-separated list of tokens for batch request
    token_list = []
    for token_address, _ in uncached_tokens:
        token_address = to_checksum_address(token_address.lower())
        token_list.append(f"{network}:{token_address}")

    all_params = ",".join(token_list)

    # Limit the URL length to avoid issues
    if len(all_params) > 2000:
        # Split into smaller batches
        batch_size = 25
        batch_results_all = []
        for i in range(0, len(uncached_tokens), batch_size):
            batch = uncached_tokens[i : i + batch_size]
            batch_results = get_erc20_prices_in_usd(chain_id, batch, timestamp)
            batch_results_all.extend(batch_results)

        # Fill in the None placeholders with batch results
        batch_idx = 0
        for i, r in enumerate(results):
            if r is None:
                results[i] = batch_results_all[batch_idx]
                batch_idx += 1
        return results

    # Determine API endpoint
    if timestamp:
        all_uris = (
            f"https://coins.llama.fi/prices/historical/"
            f"{timestamp}/{all_params}"
        )
    else:
        all_uris = f"https://coins.llama.fi/prices/current/{all_params}"

    try:
        # Use shared sync client for pooling and consistent timeouts
        from votemarket_toolkit.shared.services.http_client import get_client

        client = get_client()
        response = client.get(all_uris)
        response.raise_for_status()
        all_prices = response.json()

        if "coins" not in all_prices or not all_prices["coins"]:
            # API returned no data
            for i in range(len(results)):
                if results[i] is None:
                    results[i] = ("0.00", 0)
            return results

        prices = all_prices["coins"]

        # Process each uncached token
        for i, (token_address, unformatted_amount) in enumerate(token_amounts):
            if results[i] is not None:
                continue

            token_address = to_checksum_address(token_address.lower())
            token_key = f"{network}:{token_address}"
            price_info = prices.get(token_key)

            if price_info:
                decimals = int(price_info["decimals"])
                amount = int(unformatted_amount)
                token_price = float(price_info["price"])
                price = token_price * (amount / 10**decimals)
                results[i] = ("{:,.2f}".format(price), price)

                # Cache the result
                cache_key = (
                    f"{network}:{token_address}:{timestamp or 'current'}"
                )
                _price_cache[cache_key] = (token_price, current_time, decimals)
            else:
                results[i] = ("0.00", 0)

    except httpx.RequestError as e:
        print(f"Error fetching prices from DefiLlama: {e}")
        for i in range(len(results)):
            if results[i] is None:
                results[i] = ("0.00", 0)

    return results
