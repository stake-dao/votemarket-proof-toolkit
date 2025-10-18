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

## Services

### CampaignService
Fetch and manage campaign data, lifecycle status, and proof insertion.

```python
from votemarket_toolkit.campaigns import CampaignService

service = CampaignService()
campaigns = await service.get_campaigns(chain_id=42161, platform_address="0x...")
```

### AnalyticsService
Access historical performance metrics from the VoteMarket analytics repository.

```python
from votemarket_toolkit.analytics import get_analytics_service

analytics = get_analytics_service()
history = await analytics.fetch_gauge_history("curve", "0x...")
```

### CampaignOptimizer
Calculate optimal campaign parameters using market data and historical performance.

```python
from votemarket_toolkit.analytics import get_campaign_optimizer

optimizer = get_campaign_optimizer()
result = await optimizer.calculate_optimal_campaign(
    protocol="curve",
    gauge="0x...",
    reward_token="0x...",
    chain_id=1,
    total_reward_tokens=10000
)
```

### VoteMarketProofs
Generate merkle proofs for user and gauge rewards.

```python
from votemarket_toolkit.proofs import VoteMarketProofs

proofs = VoteMarketProofs(chain_id=1)
gauge_proof = proofs.get_gauge_proof("curve", "0x...", epoch, block_number)
user_proof = proofs.get_user_proof("curve", "0x...", "0x...", block_number)
```

### Web3Service
Multi-chain Web3 connections with contract interaction utilities.

```python
from votemarket_toolkit.shared.services import Web3Service

web3 = Web3Service.get_instance(chain_id=1)
contract = web3.get_contract(address, "vm_platform")
```

### LaPosteService
Handle wrapped/native token conversions for cross-chain rewards.

```python
from votemarket_toolkit.shared.services.laposte_service import laposte_service

native_tokens = await laposte_service.get_native_tokens(chain_id, ["0x..."])
token_info = await laposte_service.get_token_info(chain_id, "0x...")
```

### VotesService
Fetch and cache voting data for gauges.

```python
from votemarket_toolkit.votes.services import VotesService

votes = VotesService()
gauge_votes = await votes.get_gauge_votes("curve", "0x...", start_block, end_block)
```

## Configuration

Create `.env` file with RPC endpoints:

```bash
ETHEREUM_MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
ARBITRUM_MAINNET_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
```

## Streamlit UI

Web interface for campaigns, proofs, and analytics.

```bash
# Run with UV
uv run streamlit run streamlit_ui/app.py

# Run with pip  
streamlit run streamlit_ui/app.py
```

See [streamlit_ui/README.md](streamlit_ui/README.md) for details.

## Examples

See [examples/python](examples/python/) for complete usage examples:

- `campaigns/list_all.py` – Fetch campaigns across protocols with periods and rewards
- `users/check_status.py` – Check user proof status (block data, gauge data, user votes)
- `proofs/generate.py` – Build gauge and user proofs for claims
- `data/calculate_efficiency.py` – Model optimal `max_reward_per_vote` values

### Check User Eligibility

Check if a user has claimable rewards across all campaigns:

```bash
# Check eligibility for all campaigns in a protocol
make check-user-eligibility USER=0x... PROTOCOL=curve

# Filter by specific gauge
make check-user-eligibility USER=0x... PROTOCOL=curve GAUGE=0x...

# Filter by chain
make check-user-eligibility USER=0x... PROTOCOL=balancer CHAIN_ID=42161

# Show only active campaigns
make check-user-eligibility USER=0x... PROTOCOL=curve STATUS=active
```

This command checks pre-generated proof data from the [VoteMarket API](https://github.com/stake-dao/api/tree/main/api/votemarket) to determine which periods have claimable rewards.

## Development

```bash
# Clone repository
git clone https://github.com/stake-dao/votemarket-proof-toolkit
cd votemarket-proof-toolkit

# Install dependencies
uv sync

# Run examples
uv run examples/python/data/calculate_efficiency.py
uv run examples/python/data/get_token_prices.py

# Format and lint
make format              # Format all code
make format FILE=path    # Format specific file

# Build and publish
make build               # Build package
make test-build          # Test build locally
make deploy              # Deploy to PyPI

# Development commands (see Makefile for full list)
make list-campaigns CHAIN_ID=42161 PLATFORM=0x...
make get-active-campaigns PROTOCOL=curve
make check-user-eligibility USER=0x... PROTOCOL=curve [GAUGE=0x...] [CHAIN_ID=1] [STATUS=active]
```

## License

AGPL-3.0 License - see [LICENSE](LICENSE)
