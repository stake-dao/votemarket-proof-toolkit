# VoteMarket Toolkit

Python SDK for VoteMarket - campaign management, proofs, and analytics.

[![PyPI version](https://badge.fury.io/py/votemarket-toolkit.svg)](https://badge.fury.io/py/votemarket-toolkit)
[![Python](https://img.shields.io/pypi/pyversions/votemarket-toolkit.svg)](https://pypi.org/project/votemarket-toolkit/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## Installation

```bash
pip install votemarket-toolkit
```

## Quick Start

```python
from votemarket_toolkit.campaigns.service import CampaignService
from votemarket_toolkit.shared import registry

# Get platform address
curve_platform = registry.get_platform("curve", chain_id=42161)

# Fetch campaigns
service = CampaignService()
campaigns = await service.get_campaigns(
    chain_id=42161,
    platform_address=curve_platform,
    campaign_id=97
)
```

## Features

- **Campaign Management**: Fetch, create, and manage VoteMarket campaigns
- **Proof Generation**: Generate merkle proofs for reward claims
- **Analytics**: Analyze historical performance and optimize parameters
- **Multi-chain**: Supports Ethereum, Arbitrum, and other networks
- **Registry**: Built-in platform and gauge registries

## Configuration

Create `.env` file with RPC endpoints:

```bash
ETHEREUM_MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
ARBITRUM_MAINNET_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
```

## Examples

See [examples/python](examples/python/) for complete usage examples:

- `all_campaigns.py` - Fetch all campaigns across protocols
- `check_user_status.py` - Check user eligibility and rewards
- `generate_proofs.py` - Generate claim proofs
- `compute_campaign.py` - Optimize campaign parameters

## Development

```bash
# Clone repository
git clone https://github.com/stake-dao/votemarket-proof-toolkit
cd votemarket-proof-toolkit

# Install dependencies
uv sync

# Run examples
uv run examples/python/compute_campaign.py

# Format code
uv run black .
uv run ruff check --fix .

# Build package
uv build
```

## License

AGPL-3.0 License - see [LICENSE](LICENSE)
