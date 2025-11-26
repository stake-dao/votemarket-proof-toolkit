# Python SDK Examples

Structured, ready-to-run samples showcasing the VoteMarket Python SDK. Examples are grouped into a few broad folders so it’s easy to scan.

## Directory Overview
- `campaigns/` – fetch, create, manage, and close campaigns
- `data/` – analytics utilities and market data helpers
- `proofs/` – proof generation workflows
- `users/` – user eligibility checks

## Example Catalog
### Campaigns
- `campaigns/list_all.py` – list every active campaign (Curve, Balancer, Pendle, PancakeSwap) with periods, rewards, and status; saves to `output/all_campaigns.json`.
- `campaigns/by_manager.py` – fetch campaigns for a specific manager address.
- `campaigns/create_campaign_l1.py` – launch a campaign from L1 using the remote manager and CCIP fees.
- `campaigns/create_campaign_l2.py` – launch a campaign directly on Arbitrum.
- `campaigns/manage_campaign_l1.py` – extend or top up an existing campaign from L1.
- `campaigns/manage_campaign_l2.py` – manage a campaign directly on Arbitrum (requires wrapped rewards).
- `campaigns/close_campaign.py` – close and settle a campaign.

### Data
- `data/calculate_efficiency.py` – compute `max_reward_per_vote` targets across supported protocols.
- `data/get_token_prices.py` – fetch ERC-20 token prices through the toolkit pricing service.

### Proofs
- `proofs/generate.py` – generate user and gauge proofs and export them as JSON payloads.

### Users
- `users/check_status.py` – verify whether an address can claim rewards for a campaign.

## Running Examples
```bash
# Install dependencies
uv sync

# Execute any example
uv run examples/python/campaigns/list_all.py
uv run examples/python/campaigns/create_campaign_l1.py
```

All scripts honour the standard `.env` variables (e.g. `ETHEREUM_MAINNET_RPC_URL`, `ARBITRUM_MAINNET_RPC_URL`) and optional overrides such as `VOTEMARKET_MANAGER_ADDRESS` and `VOTEMARKET_REMOTE_MANAGER_ADDRESS` so you can point to your own infrastructure without editing the files.

## Environment Setup
Create a `.env` file in the project root with the required RPC endpoints:
```
ETHEREUM_MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
ARBITRUM_MAINNET_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
```
