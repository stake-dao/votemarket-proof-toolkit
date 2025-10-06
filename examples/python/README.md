# Python SDK Examples

Complete examples demonstrating VoteMarket SDK functionality.

## Available Examples

### 1. all_campaigns.py
Fetch all campaigns with periods and status:
- Lists campaigns from all protocols (Curve, Balancer, Pancakeswap, Pendle)
- Shows periods and reward amounts
- Includes campaign status information
- Saves everything to `all_campaigns.json`

### 2. check_user_status.py
Check if a specific user is eligible for campaign rewards:
- Verifies voting eligibility
- Shows reward amounts
- Checks claim status

### 3. generate_proofs.py
Generate proofs for campaign claims:
- Creates user voting proofs
- Generates gauge weight proofs
- Saves proofs in JSON format

### 4. compute_campaign.py
**Optimize campaign parameters based on market data:**
- Analyzes your gauge's historical performance (EMA smoothed)
- Compares to current market rates (robust statistics)
- Calculates optimal `max_reward_per_vote`
- Shows budget analysis (are you over/under-budgeted?)
- Provides market positioning vs peers

**Example output:**
```
Budget Analysis:
  • Your budget: 30,000 tokens
  • Tokens needed: 9,062 tokens to achieve $0.001185/vote
  • ⚠ Over-budgeted by 70%

  💡 You can reduce budget to 9,062 tokens to save 20,938 tokens
```

## Running Examples

```bash
# Setup
uv sync

# Run any example
uv run examples/python/all_campaigns.py
uv run examples/python/check_user_status.py
uv run examples/python/generate_proofs.py
```

## Environment Setup

Create `.env` in the project root:
```
ETHEREUM_MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
ARBITRUM_MAINNET_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
```