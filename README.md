# VoteMarket Toolkit

⚙️ Python SDK and CLI tools for interacting with VoteMarket campaigns and proofs

[![PyPI version](https://badge.fury.io/py/votemarket-toolkit.svg)](https://badge.fury.io/py/votemarket-toolkit)
[![Python](https://img.shields.io/pypi/pyversions/votemarket-toolkit.svg)](https://pypi.org/project/votemarket-toolkit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

```bash
pip install votemarket-toolkit
```

## Quick Start

### 🎯 Interactive Mode (New!)

Commands now support **interactive selection** - no need to memorize addresses!

```bash
# Interactive platform and campaign selection
make user-campaign-status USER_ADDRESS=0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6

# Browse all available platforms interactively
make list-campaigns
```

### CLI Commands (Direct Mode)

```bash
# Check if a user can claim rewards from a campaign
make user-campaign-status \
  PLATFORM=0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5 \
  CAMPAIGN_ID=97 \
  USER_ADDRESS=0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6

# List all campaigns on a platform
make list-campaigns PLATFORM=0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5
```

See [Commands Documentation](votemarket_toolkit/commands/README.md) for all available commands.

### Python SDK

```python
from votemarket_toolkit.campaigns.service import campaign_service
from votemarket_toolkit.shared import registry

# Get platform addresses
curve_platform = registry.get_platform("curve", chain_id=42161)

# Check campaign status
campaigns = await campaign_service.get_campaigns(
    chain_id=42161,
    platform_address=curve_platform,
    campaign_id=97
)
```

## Features

- 🎯 **Interactive Selection**: Browse and select platforms/campaigns without memorizing addresses
- 🔐 **Proof Generation**: User and gauge proofs for reward claims
- 📊 **Campaign Management**: Query and analyze VoteMarket campaigns
- 🔍 **Proof Status Checking**: Verify if users can claim rewards
- 🔄 **Multi-protocol Support**: Curve, Balancer, Frax, FXN, Pendle
- ⛓️ **Multi-chain**: Ethereum, Arbitrum, Optimism, Polygon, Base
- 📝 **Multiple Output Formats**: Table, JSON, CSV

## Project Structure

```
votemarket-proof-toolkit/
├── votemarket_toolkit/       # Python SDK package
│   ├── campaigns/           # Campaign management
│   ├── proofs/             # Proof generation
│   ├── contracts/          # Contract interactions
│   ├── shared/             # Shared utilities & registry
│   └── commands/           # CLI commands (see README)
├── examples/               # Usage examples
│   ├── python/            # Python examples
│   └── typescript/        # TypeScript reference
├── docs/                  # Documentation
└── tests/                 # Test suite
```

## Requirements

- Python >=3.10
- Web3 RPC endpoint (Alchemy, Infura, etc.)

## Configuration

Create a `.env` file:
```env
ETHEREUM_MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
ARBITRUM_MAINNET_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
```

## Documentation

- **[Commands Reference](votemarket_toolkit/commands/README.md)** - All CLI commands with examples
- [Development Guide](DEVELOPMENT.md) - Setup for contributors
- [Python Examples](examples/python/) - SDK usage examples
- [TypeScript Examples](examples/typescript/) - Reference implementations

## License

MIT License - see [LICENSE](LICENSE)