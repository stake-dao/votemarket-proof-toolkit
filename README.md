# VoteMarket Toolkit

⚙️ Python SDK and CLI tools for interacting with VoteMarket campaigns and proofs

[![PyPI version](https://badge.fury.io/py/votemarket-toolkit.svg)](https://badge.fury.io/py/votemarket-toolkit)
[![Python](https://img.shields.io/pypi/pyversions/votemarket-toolkit.svg)](https://pypi.org/project/votemarket-toolkit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Setup

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup project
git clone https://github.com/stake-dao/votemarket-proof-toolkit
cd votemarket-proof-toolkit
./setup.sh
```

## Usage

```bash
# SDK Examples (see examples/python/)
uv run examples/python/list_all_campaigns.py
uv run examples/python/check_user_status.py

# CLI Commands
uv run -m votemarket_toolkit.commands.list_campaigns
uv run -m votemarket_toolkit.commands.user_campaign_status --user 0x...
```

## Quick Start

```bash
# 1. Setup (installs UV, Python, and dependencies)
git clone https://github.com/stake-dao/votemarket-proof-toolkit
cd votemarket-proof-toolkit
./setup.sh

# 2. Run examples
uv run examples/python/get_campaign.py curve 97
```



### Commands 

```bash
# Check if user can claim rewards
uv run -m votemarket_toolkit.commands.user_campaign_status \
  --platform 0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5 \
  --campaign-id 97 \
  --user 0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6

# List campaigns on a platform
uv run -m votemarket_toolkit.commands.list_campaigns --platform 0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5
```

See [Commands Documentation](votemarket_toolkit/commands/README.md) for all available commands.

### As Python SDK

```python
from votemarket_toolkit.campaigns.service import CampaignService
from votemarket_toolkit.shared import registry

# Get platform address
curve_platform = registry.get_platform("curve", chain_id=42161)

# Get campaign
service = CampaignService()
campaigns = await service.get_campaigns(
    chain_id=42161,
    platform_address=curve_platform,
    campaign_id=97
)
```

## Configuration

Add RPC endpoints to `.env`:
```
ETHEREUM_MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
ARBITRUM_MAINNET_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
```

## Commands

```bash
# Add dependencies
uv add package-name

# Run tests
uv run pytest

# Format code
uv run black .
uv run ruff check --fix .

# Build package
uv build
```

## Documentation

- **[Commands Reference](votemarket_toolkit/commands/README.md)** - All CLI commands with examples
- [Development Guide](DEVELOPMENT.md) - Setup for contributors
- [Python Examples](examples/python/) - SDK usage examples
- [TypeScript Examples](examples/typescript/) - Reference implementations

## License

MIT License - see [LICENSE](LICENSE)