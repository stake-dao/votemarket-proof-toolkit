# Python Examples

This directory contains Python examples demonstrating how to use the VoteMarket toolkit SDK.

## Available Examples

- **`get_campaign.py`** - Fetch and display campaign data from VoteMarket contracts
- **`using_registry.py`** - Demonstrate how to use the registry to find platform addresses

## Installation

Make sure the votemarket-toolkit is installed:

```bash
# From PyPI
pip install votemarket-toolkit

# Or for development (from repository root)
pip install -e .

# Or run directly from repository without installation
cd /path/to/votemarket-proof-toolkit
PYTHONPATH=. python examples/python/using_registry.py
```

## Running Examples

### Get Campaign Data

```bash
# Get campaign by ID from any platform
python get_campaign.py curve 3

# Get campaign from specific platform
python get_campaign.py curve 3 0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5
```

### Use Registry

```bash
python using_registry.py
```

## Environment Variables

Create a `.env` file in the repository root:

```env
ETHEREUM_MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
ARBITRUM_MAINNET_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
```

## Notes

These examples use the actual VoteMarket SDK (`votemarket_toolkit`) package. For TypeScript integration examples, see `../typescript/`.