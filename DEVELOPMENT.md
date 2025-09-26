# VoteMarket Toolkit - Development Guide

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Building & Publishing](#building--publishing)
- [Testing](#testing)
- [Contributing](#contributing)
- [Advanced Usage](#advanced-usage)

## Development Setup

### Prerequisites

- Python >=3.10
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Installation

```bash
# Clone repository
git clone https://github.com/stake-dao/votemarket-proof-toolkit.git
cd votemarket-proof-toolkit

# Install development dependencies
make install-dev

# Verify installation
make help
```

### Configuration

Create `.env` file:
```env
ETHEREUM_MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/API_KEY
ARBITRUM_MAINNET_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/API_KEY
```

## Project Structure

```
votemarket-proof-toolkit/
├── votemarket_toolkit/         # Main Python package
│   ├── campaigns/              # Campaign management
│   ├── proofs/                 # Proof generation
│   ├── contracts/              # Contract interactions
│   ├── shared/                 # Shared utilities
│   └── commands/               # CLI commands
├── docs/                       # Documentation
│   ├── examples/               # Tutorial examples
│   └── guides/                 # Usage guides
├── examples/                   # Usage examples
│   ├── python/                 # Python SDK examples
│   └── typescript/             # TypeScript reference implementations
├── dist/                       # Build artifacts
└── tests/                      # Test suite
```

## Building & Publishing

### Prerequisites for Publishing

- PyPI account and API token
- twine: `uv pip install twine`

### Build Process

#### 1. Update Version

Edit `pyproject.toml`:
```toml
[project]
version = "0.0.2"  # Update version
```

#### 2. Build Package

```bash
# Clean previous builds
make clean-build

# Build package
make build
```

This creates:
- `dist/votemarket_toolkit-X.X.X-py3-none-any.whl`
- `dist/votemarket_toolkit-X.X.X.tar.gz`

#### 3. Test Locally

```bash
# Create test environment
uv venv test-env
source test-env/bin/activate

# Install built package
uv pip install dist/votemarket_toolkit-*.whl

# Test imports
python -c "from votemarket_toolkit.shared import registry; print('✅ Success')"

# Clean up
deactivate
rm -rf test-env
```

### Publishing to PyPI

#### Configure Credentials

Create `~/.pypirc`:
```ini
[pypi]
  username = __token__
  password = pypi-YOUR-API-TOKEN
```

Set permissions:
```bash
chmod 600 ~/.pypirc
```

#### Deploy

```bash
# Deploy to PyPI
make deploy

# Or manually
uv run twine upload dist/*
```

#### Post-Deployment

```bash
# Tag release
git tag v0.0.2
git push origin v0.0.2

# Verify on PyPI
pip install votemarket-toolkit
```

### Publishing Checklist

- [ ] Run formatter: `make format`
- [ ] Update version in `pyproject.toml`
- [ ] Clean builds: `make clean-build`
- [ ] Build: `make build`
- [ ] Test locally
- [ ] Deploy: `make deploy`
- [ ] Git tag: `git tag vX.X.X`
- [ ] Push tags: `git push --tags`

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run specific test
uv run pytest tests/test_proofs.py

# Run with coverage
uv run pytest --cov=votemarket_toolkit
```

### Integration Tests

```bash
# Run integration tests
make integration

# Run examples
make run-examples
```

## Contributing

### Code Style

```bash
# Format code
make format

# Lint
make lint
```

### Making Changes

1. Create feature branch
2. Make changes
3. Run tests
4. Submit PR

## Advanced Usage

### Using the Makefile

```bash
# Generate user proof
make user-proof PROTOCOL=curve GAUGE_ADDRESS=0x... USER_ADDRESS=0x... BLOCK_NUMBER=12345678

# Generate gauge proof  
make gauge-proof PROTOCOL=curve GAUGE_ADDRESS=0x... CURRENT_EPOCH=1234567890 BLOCK_NUMBER=12345678

# Get block info
make block-info BLOCK_NUMBER=12345678

# Get active campaigns
make get-active-campaigns CHAIN_ID=1 PLATFORM=0x...
```

### Python Integration

```python
from votemarket_toolkit.proofs.manager import ProofManager
from votemarket_toolkit.campaigns.services import CampaignService
from votemarket_toolkit.shared.registry import Registry
from votemarket_toolkit.shared.constants import PROTOCOLS

# Initialize registry
registry = Registry()

# Get platform addresses
curve_v2 = registry.get_platform("curve", chain_id=42161, version="v2")

# Generate proofs
proof_manager = ProofManager()
user_proof = proof_manager.generate_user_proof(
    protocol="curve",
    gauge_address="0x...",
    user_address="0x...",
    block_number=12345678
)

# Campaign management
campaign_service = CampaignService(chain_id=1)
campaigns = campaign_service.get_active_campaigns(platform_address="0x...")
```

### Understanding Block Numbers

The `BLOCK_NUMBER` parameter should match the block set in the VoteMarket oracle for the specific period.

Get correct block numbers:
```bash
make get-epoch-blocks CHAIN_ID=1 PLATFORM=0x... EPOCHS=1234,1235,1236
```

## Troubleshooting

### Build Issues

```bash
# Update uv
uv self update

# Clear caches
make clean
uv cache clean
```

### Import Issues

```bash
# Check package structure
tar -tzf dist/votemarket_toolkit-*.tar.gz | head -20
```

### Common Errors

- **Version conflicts**: Always increment version, PyPI doesn't allow overwrites
- **Missing dependencies**: Ensure `.env` is configured with RPC URLs
- **Import errors**: Check Python version >=3.10

## Support

- [GitHub Issues](https://github.com/stake-dao/votemarket-proof-toolkit/issues)
- [Documentation](https://github.com/stake-dao/votemarket-proof-toolkit/tree/main/docs)