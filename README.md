# VoteMarket Toolkit

Python SDK for VoteMarket - campaign management, proofs, and analytics.

[![PyPI version](https://badge.fury.io/py/votemarket-toolkit.svg)](https://badge.fury.io/py/votemarket-toolkit)
[![Python](https://img.shields.io/pypi/pyversions/votemarket-toolkit.svg)](https://pypi.org/project/votemarket-toolkit/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## Installation

```bash
pip install votemarket-toolkit
```

### Development Prerequisites

For development, this project uses [uv](https://github.com/astral-sh/uv) for fast, reliable dependency management.

**Install uv:**

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Alternative: via pip
pip install uv
```

**Alternative: Traditional pip/venv workflow**

If you prefer not to use uv, you can use standard Python tools:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate  # Windows

# Install package in editable mode
pip install -e ".[dev]"

# Run commands directly
python -m votemarket_toolkit.cli --help
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
# Required for all chains
ETHEREUM_MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
ARBITRUM_MAINNET_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
OPTIMISM_MAINNET_RPC_URL=https://opt-mainnet.g.alchemy.com/v2/YOUR_KEY
BASE_MAINNET_RPC_URL=https://base-mainnet.g.alchemy.com/v2/YOUR_KEY
POLYGON_MAINNET_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
BSC_MAINNET_RPC_URL=https://bsc-dataseed.binance.org/
```

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

## Unified CLI

You can use the unified CLI instead of individual scripts.

Examples:

- Generate a user proof
  uv run -m votemarket_toolkit.cli proofs-user --protocol curve --gauge-address 0x... --user-address 0x... --block-number 18500000 [--chain-id 1]

- Generate a gauge proof
  uv run -m votemarket_toolkit.cli proofs-gauge --protocol curve --gauge-address 0x... --current-epoch 1699920000 --block-number 18500000 [--chain-id 1]

- List active campaigns
  uv run -m votemarket_toolkit.cli campaigns-active --protocol curve --chain-id 42161
  uv run -m votemarket_toolkit.cli campaigns-active --platform 0x... --chain-id 42161

- Check a user’s eligibility
  uv run -m votemarket_toolkit.cli users-eligibility --user 0x... --protocol curve [--gauge 0x...] [--chain-id 42161] [--status active|closed|all]

When installed from PyPI, the CLI is available as `votemarket`:

- votemarket proofs-user --protocol curve --gauge-address 0x... --user-address 0x... --block-number 18500000

## Development

```bash
# Clone repository
git clone https://github.com/stake-dao/votemarket-proof-toolkit
cd votemarket-proof-toolkit

# Install dependencies (requires uv - see below)
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

## Bulk proof generation (opt-in)

`VoteMarketProofs.get_proofs_bulk()` groups the storage keys of many gauges and
users into a few `eth_getProof` calls on the gauge controller instead of one
call per proof. The generated proofs are byte-identical to `get_gauge_proof()`
/ `get_user_proof()` (see `tests/unit/test_bulk_proofs.py`); failing chunks are
split in half down to single proofs.

```python
result = proofs.get_proofs_bulk(
    "curve",
    block_number,
    gauge_epochs=[(gauge, epoch)],
    users=[(gauge, user) for user in users],
    keys_per_call=100,
)
result.data.gauge_proofs[(gauge.lower(), epoch)]  # GaugeProof
result.data.user_proofs[(gauge.lower(), user.lower())]  # UserProof
```

The proof pipeline can use it behind a flag (default stays per-request):

```bash
uv run scripts/vm_active_proofs.py temp/all_platforms.json <epoch> --bulk-proofs [--keys-per-call 100]
# or: VM_BULK_PROOFS=1 VM_BULK_KEYS_PER_CALL=100
```

Provider notes (measured on Alchemy, 2026-08-31): `eth_getProof` accepts at most
1024 storage keys per call and is billed 20 CU per call regardless of the number
of keys (verified on the usage dashboard with 1, 100 and 1000 keys). On the app
tested (Free tier) `eth_getProof` only served blocks up to ~128 behind the head
while archive `eth_call` worked, so proofs must be generated shortly after the
oracle block is set unless the plan/provider serves archive proofs.

To check both modes against each other on real gauges (active campaigns, oracle
block of the current epoch) and see the RPC call counts:

```bash
uv run scripts/compare_bulk_proofs.py --protocol curve --chain-id 42161 --max-gauges 3
```

## Batch verifier artifacts (node bags)

The `BatchVerifier` (`contracts-monorepo/packages/votemarket/src/verifiers/BatchVerifier.sol`)
proves many accounts of a gauge in one call from a single deduplicated *node bag*
instead of one proof blob per account. In bulk mode the pipeline builds those
bags from the same `eth_getProof` responses (no extra RPC call) for the protocols
the batch verifier supports — curve, balancer, fxn (pendle/yb keep their own
verifiers) — and publishes them **next to** the legacy fields, which are
untouched: the legacy verifier and self-serve users keep working from the same
files. Artifact generation is best-effort and can never break the legacy
publication. The migrated automation-jobs consumer requires these artifacts for
Curve, Balancer and FXN: missing or unusable required batches stop the job, with
no legacy fallback. See the [current rollout checklist](docs/batch-verifier-rollout.md)
for deployment, both Oracle authorizations and activation on the existing pipeline.

```jsonc
// <platform>/<chain>/<gauge>.json — per gauge, for setAccountDataBatch(gauge, epoch, accounts, node_bag)
"batch": {
  "version": 1,
  "verifier": "BatchVerifier",
  "block_number": 25883568,
  "accounts_total": 25,                 // every account of the gauge's legacy fields is covered
  "observed_storage_root": "0x…",       // diagnostic only, see below
  "chunks": [{"accounts": ["0x…"], "node_bag": "0x…", "bag_bytes": 85055, "calldata_bytes": 85860}, …]
}
// <platform>/<chain>/index.json — per platform, for setPointDataBatch(gauges, epoch, node_bag)
"batch_points": {"version": 1, "verifier": "BatchVerifier", "block_number": 25883568,
                 "observed_storage_root": "0x…", "missing_gauges": [],
                 "chunks": [{"gauges": ["0x…"], "node_bag": "0x…", "bag_bytes": 2323, "calldata_bytes": 2532}]}
```

- **Coverage is all-or-nothing for the published gauge inventory**: a `batch` is
  published only when every account present in the gauge's legacy fields (eligible
  and listed users) has trie nodes at the platform's block; otherwise the gauge has
  no `batch`. `batch_points.missing_gauges` names gauges a point bag does not cover.
  Automation-jobs fails if any required member lacks batch coverage, even when its
  legacy blob exists. This cannot detect users omitted before the inventory was
  built. Separately, the producer can report success without required bags, and the
  API wrapper can omit bulk mode; both publication issues remain open. Accounts are
  sorted (lowercase) so chunks are canonical across runs; the order inside a chunk
  is the order to pass on-chain.
- **Chunks are cut by encoded call size**, not by number of accounts: the ABI head,
  one 32-byte word per account and the padded bag must fit the budget — 90 KB on
  Arbitrum (sequencer limit ~95 KB, about 20 accounts today), 124 KB on Optimism
  (131 KB limit); override with `--batch-max-bytes` or `VM_BATCH_MAX_BYTES`. The
  bot must still validate the final serialized transaction (a Weiroll wrapper adds
  bytes). Each chunk carries its own minimal bag: reusing a gauge-wide bag for a
  subset would not shrink the transaction.
- Artifacts are published only for platforms anchored at the chain's published
  header block (the verifier registers its storage root from that header), and
  only when every response of the run reported the same controller `storageHash`
  (a run where responses disagreed or carried no root gets no artifacts).
  `observed_storage_root` is that pinned value and is **diagnostic only**: the
  batch verifier proves the root from the anchored block header and stores it in
  `Oracle.epochBlockNumber(epoch).stateRootHash`, as the legacy verifiers do;
  no batch call accepts this value — at most compare it with
  `storageRootByEpoch(epoch)` (a getter over the Oracle field). Root registration
  requires the verifier's Oracle block-number-provider role; inserting votes and
  weights also requires its data-provider role. Re-registering validates the full
  header/account proof, accepts an identical root and rejects a conflicting root.
- Bag encoding follows the on-chain contract (nodes deduplicated and sorted by
  keccak, embedded nodes under 32 bytes dropped except stack roots) and is pinned
  byte-for-byte to the Solidity reference helper `BagBuilder.sol` in
  `tests/unit/test_node_bag.py`. `scripts/export_batch_bags.py` builds real bags
  from a live `eth_getProof` for an end-to-end check with the Solidity library.

## Proof regression tests

Proof entry points and the batch exporter trim and lowercase protocol names
before selecting storage layouts; unknown names fail before any proof RPC.
Curve always uses slots `11` (last vote), `9` (slope/end) and `12` (point weights),
including its additional storage-slot hash. `curve`, `CURVE`, `Curve` and
`" curve "` therefore produce identical proofs.

`BatchStacks` collects one protocol and one epoch. The first point proof binds
its epoch, and a record containing mixed or different epochs fails before
changing its state. Use another collector for another epoch.

Run the deterministic Python-to-Solidity test against a contracts checkout:

```sh
VOTEMARKET_CONTRACTS_PATH=/absolute/path/to/contracts-monorepo \
REQUIRE_BATCH_VERIFIER_TEST=1 PYTHON_DOTENV_DISABLED=1 \
uv run --frozen --extra dev pytest -q -s tests/integration/test_curve_batch_verifier.py
```

Install Forge first. The test compiles the unmodified `BatchVerifier`, `Oracle`
and their proof libraries with Solidity 0.8.28, then runs the real exporter for
all four spellings against recorded block 21134723 proofs. It checks fixed
storage paths and four nonzero values written to the Oracle. It needs no RPC
endpoint, private key or live transaction. `SOLC_BINARY` can select an already
installed compiler for a fully offline run. With `REQUIRE_BATCH_VERIFIER_TEST=1`,
missing Forge or a missing contracts checkout is an error, not a skipped test.

Run these checks manually against the intended toolkit and contracts revisions.
The [rollout checklist](docs/batch-verifier-rollout.md#manual-validation-and-order) also gives the
recorded Foundry and automation tests, plus the Curve and FXN mainnet-getter tests.
Those mainnet tests generate proofs through Python, insert them into a local
verifier/Oracle and compare the resulting data and votes without a fork.

## License

AGPL-3.0 License - see [LICENSE](LICENSE)
