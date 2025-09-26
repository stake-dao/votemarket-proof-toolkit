# VoteMarket Toolkit - Code Structure

## Overview

This document describes the improved code organization for the VoteMarket toolkit, designed for clarity, maintainability, and single responsibility.

## Directory Structure

```
votemarket_toolkit/
├── campaigns/              # Campaign management
│   ├── __init__.py
│   ├── models.py          # Data models & types
│   └── service.py         # Campaign operations
├── data/                  # Data services
│   ├── __init__.py
│   ├── eligibility.py    # User eligibility checks
│   └── oracle.py          # Oracle block queries
├── proofs/               # Proof generation
│   ├── __init__.py
│   ├── manager.py        # Proof manager
│   ├── types.py          # Proof types
│   └── generators/       # Proof generators
├── contracts/            # Smart contract interaction
│   ├── __init__.py
│   ├── reader.py         # Contract reading
│   └── compiler.py       # Contract compilation
├── shared/               # Shared utilities
│   ├── __init__.py
│   ├── constants.py      # Global constants
│   ├── registry.py       # Contract registry
│   ├── types.py          # Shared types
│   └── services/         # Shared services
├── votes/                # Vote indexing & management
│   ├── models/           # Vote data models
│   └── services/         # Vote services
├── commands/             # CLI commands
├── external/             # External integrations
├── resources/            # Static resources (ABIs, bytecode)
├── scripts/              # Standalone scripts
└── utils/                # General utilities
```

## Module Descriptions

### campaigns/
**Purpose**: Manage VoteMarket campaign operations

- `models.py`: Campaign data models, status enums, type definitions
- `service.py`: High-level campaign operations (fetch, status calculation, proof checking)

**Example Usage**:
```python
from votemarket_toolkit.campaigns import CampaignService, CampaignStatus

service = CampaignService()
campaigns = await service.get_active_campaigns(chain_id=1, platform="0x...")
```

### data/
**Purpose**: Handle blockchain data queries

- `eligibility.py`: Determine which users can claim rewards
- `oracle.py`: Query canonical block numbers from oracle

**Example Usage**:
```python
from votemarket_toolkit.data import EligibilityService, OracleService

# Check user eligibility
eligibility = EligibilityService(chain_id=1)
eligible_users = await eligibility.get_eligible_users(
    protocol="curve",
    gauge_address="0x...",
    current_epoch=1699920000,
    block_number=18500000
)

# Get oracle blocks
oracle = OracleService(chain_id=1)
blocks = oracle.get_epochs_block(
    chain_id=1,
    platform="0x...",
    epochs=[1699920000]
)
```

### proofs/
**Purpose**: Generate merkle proofs for reward claims

- `manager.py`: Main proof generation interface
- `types.py`: Proof data structures
- `generators/`: Individual proof generators (user, gauge, block)

### contracts/
**Purpose**: Smart contract interaction layer

- `reader.py`: Read contract state efficiently using bytecode deployment
- `compiler.py`: Compile Solidity contracts for deployment

### shared/
**Purpose**: Shared utilities and services

- `constants.py`: Network configurations, RPC URLs
- `registry.py`: Contract addresses and configurations
- `services/`: Web3 service, resource manager, etc.

## Design Principles

### 1. Single Responsibility
Each module has one clear purpose:
- `CampaignService`: Campaign operations only
- `EligibilityService`: User eligibility only  
- `OracleService`: Oracle queries only

### 2. Flat Structure
- No unnecessary nesting (removed `services/` subdirectory)
- Direct imports: `from votemarket_toolkit.campaigns import CampaignService`

### 3. Clear Naming
- `types.py` → `models.py` (clearer purpose)
- Service names describe their function

### 4. Separation of Concerns
- Data operations (`data/`) separate from business logic (`campaigns/`)
- Static resources (`resources/`) separate from code

## Import Examples

### Before (nested structure):
```python
from votemarket_toolkit.campaigns.services.campaign_service import CampaignService
from votemarket_toolkit.campaigns.services.data_service import VoteMarketDataService
from votemarket_toolkit.campaigns.types import CampaignStatus
```

### After (flat structure):
```python
from votemarket_toolkit.campaigns import CampaignService, CampaignStatus
from votemarket_toolkit.data import EligibilityService, OracleService
```

## Benefits

1. **Easier Navigation**: Flatter structure makes it easier to find code
2. **Clearer Imports**: Shorter, more intuitive import statements
3. **Better Modularity**: Each module has a single, clear responsibility
4. **Improved Maintainability**: Smaller files (~150-200 lines) are easier to maintain
5. **Standard Python Patterns**: Follows conventions from Django, Flask, FastAPI

## Migration Notes

When migrating existing code:
1. Update imports to use new paths
2. Replace `VoteMarketDataService` with `EligibilityService` or `OracleService` as appropriate
3. Import types from `campaigns.models` instead of `campaigns.types`