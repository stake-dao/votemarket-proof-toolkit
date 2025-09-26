# VoteMarket Toolkit Commands

This directory contains all CLI commands for interacting with VoteMarket campaigns and proofs.

## 🎯 Interactive Mode

Most commands now support **interactive selection** when key parameters are not provided:
- **No platform?** → Shows a list of all available platforms to choose from
- **No campaign?** → Shows active campaigns on the selected platform
- **Unknown platform?** → Prompts for chain selection

This makes the commands much easier to use without memorizing addresses!

## Available Commands

### 📊 Campaign Management

#### `user-campaign-status`
Check if a user has all necessary proofs inserted for claiming rewards from a campaign.

**Features:**
- Auto-detects chain from platform address
- Supports multiple campaigns in one command
- Multiple output formats (table, JSON, CSV)
- Brief mode for quick YES/NO answers

**Usage:**
```bash
# Interactive mode - select platform and campaign
make user-campaign-status \
  USER_ADDRESS=0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6

# Basic usage (auto-detects chain)
make user-campaign-status \
  PLATFORM=0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5 \
  CAMPAIGN_ID=97 \
  USER_ADDRESS=0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6

# Brief mode - just show if claimable
make user-campaign-status \
  PLATFORM=0x5e5C... \
  CAMPAIGN_ID=97 \
  USER_ADDRESS=0x52f5... \
  BRIEF=1

# Check multiple campaigns
make user-campaign-status \
  PLATFORM=0x5e5C... \
  CAMPAIGN_ID=97,98,99 \
  USER_ADDRESS=0x52f5... 

# Export to CSV
make user-campaign-status \
  PLATFORM=0x5e5C... \
  CAMPAIGN_ID=97 \
  USER_ADDRESS=0x52f5... \
  FORMAT=csv > results.csv

# Get JSON output for scripting
make user-campaign-status \
  PLATFORM=0x5e5C... \
  CAMPAIGN_ID=97 \
  USER_ADDRESS=0x52f5... \
  FORMAT=json
```

**Options:**
- `CHAIN_ID`: Chain ID (optional, auto-detected from platform)
- `PLATFORM`: VoteMarket platform address (optional, interactive selection if not provided)
- `CAMPAIGN_ID`: Campaign ID(s) to check (optional, interactive selection if not provided)
- `USER_ADDRESS`: User address to check proofs for (required)
- `FORMAT`: Output format - `table` (default), `json`, or `csv`
- `BRIEF`: Show brief summary only (YES/NO claimability)
- `INTERACTIVE`: Force interactive mode even if parameters provided

---

#### `list-campaigns`
List all campaigns on a VoteMarket platform with their current status.

**Usage:**
```bash
# Interactive mode - select platform from list
make list-campaigns

# List all campaigns with specific platform
make list-campaigns PLATFORM=0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5

# Show only active campaigns
make list-campaigns PLATFORM=0x5e5C... ACTIVE_ONLY=1

# Get JSON output
make list-campaigns PLATFORM=0x5e5C... FORMAT=json
```

**Options:**
- `CHAIN_ID`: Chain ID (optional, auto-detected)
- `PLATFORM`: VoteMarket platform address (optional, interactive selection if not provided)
- `FORMAT`: Output format - `table` (default) or `json`
- `ACTIVE_ONLY`: Show only active (non-closed) campaigns

---

#### `get-active-campaigns`
Get detailed information about active campaigns across protocols.

**Usage:**
```bash
# Get all active campaigns for a protocol
make get-active-campaigns PROTOCOL=curve

# Check specific platform with proof status
make get-active-campaigns \
  PLATFORM=0x5e5C... \
  CHECK_PROOFS=1

# Filter by chain
make get-active-campaigns \
  PROTOCOL=curve \
  CHAIN_ID=42161
```

**Options:**
- `CHAIN_ID`: Filter by specific chain
- `PLATFORM`: Specific platform address
- `PROTOCOL`: Protocol name (curve, balancer, etc.)
- `CHECK_PROOFS`: Check proof insertion status

---

### 🔍 Proof Generation

#### `user-proof`
Generate a proof for a user's vote on a specific gauge.

**Usage:**
```bash
make user-proof \
  PROTOCOL=curve \
  GAUGE_ADDRESS=0x26f7786de3e6d9bd37fcf47be6f2bc455a21b74a \
  USER_ADDRESS=0x52f541764e6e90eebc5c21ff570de0e2d63766b6 \
  BLOCK_NUMBER=21185919
```

**Options:**
- `PROTOCOL`: Protocol name (curve, balancer, etc.)
- `GAUGE_ADDRESS`: Address of the gauge
- `USER_ADDRESS`: Address of the user
- `BLOCK_NUMBER`: Block number for proof

---

#### `gauge-proof`
Generate a proof for gauge voting data at a specific epoch.

**Usage:**
```bash
make gauge-proof \
  PROTOCOL=curve \
  GAUGE_ADDRESS=0x26f7786de3e6d9bd37fcf47be6f2bc455a21b74a \
  CURRENT_EPOCH=1731542400 \
  BLOCK_NUMBER=21185919
```

**Options:**
- `PROTOCOL`: Protocol name
- `GAUGE_ADDRESS`: Address of the gauge
- `CURRENT_EPOCH`: Epoch timestamp
- `BLOCK_NUMBER`: Block number for proof

---

### 📝 Information & Utilities

#### `block-info`
Get detailed information about a specific block.

**Usage:**
```bash
make block-info BLOCK_NUMBER=21185919
```

---

#### `get-epoch-blocks`
Get block numbers for specific epochs.

**Usage:**
```bash
make get-epoch-blocks \
  PLATFORM=0x5e5C... \
  EPOCHS=1731542400,1732147200
```

**Options:**
- `CHAIN_ID`: Chain ID (optional if platform provided)
- `PLATFORM`: Platform address
- `EPOCHS`: Comma-separated epoch timestamps

---

#### `index-votes`
Index voting data for analysis.

**Usage:**
```bash
make index-votes \
  PROTOCOL=curve \
  GAUGE_ADDRESS=0x26f7...
```

---

### 💡 Help & Examples

#### `help`
Display help information and usage examples.

**Usage:**
```bash
make help
```

---

## Output Formats

### Table Format (Default)
Rich formatted tables with colors and clear layout. Best for human reading.

### JSON Format
Structured JSON output for programmatic consumption:
```json
{
  "campaign_id": 97,
  "chain_id": 42161,
  "user": "0x52f5...",
  "total_periods": 2,
  "claimable_periods": 2,
  "fully_claimable": true,
  "periods": [...]
}
```

### CSV Format
Comma-separated values for spreadsheet import:
```csv
campaign_id,period_num,timestamp,date,block_updated,point_data,user_slope,slope_value,claimable
97,1,1738800000,2025-02-06 01:00,True,True,True,203426989558890386,True
```

### Brief Mode
Quick summary output:
```
Campaign #97: User can claim 2/2 periods ✓
```

## Chain Support

The toolkit supports multiple chains:
- **Ethereum (1)**: Mainnet
- **Arbitrum (42161)**: L2
- **Optimism (10)**: L2
- **Polygon (137)**: L2
- **Base (8453)**: L2

Platform addresses are unique across chains, so chain ID is usually auto-detected.

## Error Handling

Commands provide helpful error messages:
- Invalid campaign IDs show the valid range
- Unknown platforms suggest specifying chain ID
- Failed RPC calls include retry suggestions

## Interactive Mode Examples

### Browse and select platforms interactively
```bash
# Shows all available platforms and lets you choose
make list-campaigns
```

### Check user status with interactive campaign selection
```bash
# Select platform and campaign interactively
make user-campaign-status USER_ADDRESS=0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6

# The command will:
# 1. Show all available platforms across all chains
# 2. Let you select a platform
# 3. Fetch and display campaigns on that platform
# 4. Let you select a campaign
# 5. Check the user's proof status for that campaign
```

### Filter platforms by chain
```bash
# Show only Arbitrum platforms
make list-campaigns CHAIN_ID=42161
```

## Automation Examples

### Check if user can claim from multiple campaigns
```bash
make user-campaign-status \
  PLATFORM=0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5 \
  CAMPAIGN_ID=97,98,99,100 \
  USER_ADDRESS=0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6 \
  BRIEF=1
```

### Export campaign list to analyze in Excel
```bash
make list-campaigns \
  PLATFORM=0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5 \
  FORMAT=json | jq -r '.[] | [.id, .gauge, .periods, .is_closed] | @csv' > campaigns.csv
```

### Quick check all claimable campaigns for a user
```bash
# First get all campaign IDs
CAMPAIGN_IDS=$(make list-campaigns PLATFORM=0x5e5C... FORMAT=json | jq -r '.[].id' | tr '\n' ',')

# Then check user status for all
make user-campaign-status \
  PLATFORM=0x5e5C... \
  CAMPAIGN_ID=$CAMPAIGN_IDS \
  USER_ADDRESS=0x52f5... \
  BRIEF=1
```