"""
Example: Fetch token prices in batch from DefiLlama.

Demonstrates fetching multiple token prices efficiently using a single API call.
"""

from votemarket_toolkit.utils.pricing import get_erc20_prices_in_usd

# Example: Get prices for multiple tokens on Ethereum mainnet
tokens = [
    ("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 10**18),  # WETH (1 token)
    ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 10**6),  # USDC (1 token)
    ("0x6B175474E89094C44Da98b954EedeAC495271d0F", 10**18),  # DAI (1 token)
    ("0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0", 10**18),  # wstETH (1 token)
]

print("Fetching prices for tokens on Ethereum...")
results = get_erc20_prices_in_usd(chain_id=1, token_amounts=tokens)

for (address, amount), (formatted, price) in zip(tokens, results):
    print(f"{address}: ${formatted} (raw: {price})")

print("\n" + "=" * 50 + "\n")

# Example: Get prices on Arbitrum
arb_tokens = [
    ("0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", 10**18),  # WETH (1 token)
    ("0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 10**6),  # USDC (1 token)
]

print("Fetching prices for tokens on Arbitrum...")
results = get_erc20_prices_in_usd(chain_id=42161, token_amounts=arb_tokens)

for (address, amount), (formatted, price) in zip(arb_tokens, results):
    print(f"{address}: ${formatted} (raw: {price})")
