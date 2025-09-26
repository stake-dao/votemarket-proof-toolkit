# VoteMarket Toolkit

⚙️ Python SDK for interacting with VoteMarket campaigns and proofs

[![PyPI version](https://badge.fury.io/py/votemarket-toolkit.svg)](https://badge.fury.io/py/votemarket-toolkit)
[![Python](https://img.shields.io/pypi/pyversions/votemarket-toolkit.svg)](https://pypi.org/project/votemarket-toolkit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

```bash
pip install votemarket-toolkit
```

## Quick Start

```python
from votemarket_toolkit.proofs import ProofManager
from votemarket_toolkit.campaigns import CampaignService
from votemarket_toolkit.shared import registry

# Get platform addresses
curve_platform = registry.get_platform("curve", chain_id=1)

# Generate user proof
proof_manager = ProofManager()
user_proof = proof_manager.generate_user_proof(
    protocol="curve",
    gauge_address="0x...",
    user_address="0x...",
    block_number=12345678
)

# Work with campaigns
campaign_service = CampaignService(chain_id=1)
campaigns = campaign_service.get_active_campaigns()
```

## Features

- 🔐 **Proof Generation**: User and gauge proofs for claim operations
- 📊 **Campaign Management**: Create, manage, and close campaigns
- 🔄 **Multi-protocol Support**: Curve, Balancer, Frax, FXN
- ⛓️ **Cross-chain**: Ethereum mainnet and Arbitrum
- 📝 **Registry System**: Easy access to contract addresses

## Project Structure

```
votemarket-proof-toolkit/
├── votemarket_toolkit/        # Python SDK package
│   ├── campaigns/            # Campaign management
│   ├── proofs/              # Proof generation
│   ├── contracts/           # Contract interactions
│   ├── shared/              # Shared utilities
│   └── commands/            # CLI commands
├── examples/                  # Usage examples
│   ├── python/              # Python usage examples
│   └── typescript/          # TypeScript reference implementations
├── docs/                    # Documentation and guides
└── tests/                   # Test suite
```

### TypeScript Integration

TypeScript developers can find reference implementations in `examples/typescript/`. These examples demonstrate:
- CCIP gas estimation in TypeScript
- Direct contract interaction patterns
- Web3.js/Ethers.js integration approaches

**Note:** The main SDK is Python-based. TypeScript examples are provided as reference implementations only.

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

- [GitHub Repository](https://github.com/stake-dao/votemarket-proof-toolkit)
- [Development Guide](https://github.com/stake-dao/votemarket-proof-toolkit/blob/main/DEVELOPMENT.md)
- [Full Documentation](https://github.com/stake-dao/votemarket-proof-toolkit/blob/main/docs/README.md)
- [Python Examples](https://github.com/stake-dao/votemarket-proof-toolkit/tree/main/examples/python)
- [TypeScript Examples](https://github.com/stake-dao/votemarket-proof-toolkit/tree/main/examples/typescript)

## License

MIT License - see [LICENSE](https://github.com/stake-dao/votemarket-proof-toolkit/blob/main/LICENSE)