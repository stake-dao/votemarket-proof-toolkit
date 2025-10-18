# VoteMarket Toolkit - Streamlit UI

A user-friendly web interface for the VoteMarket Proof Toolkit, providing easy access to campaign management, proof generation, and analytics.

## Features

### 📊 Active Campaigns
- Browse active voting campaigns across multiple chains and protocols
- View campaign details including reward tokens, periods, and status
- Check proof insertion status for claiming eligibility
- Export campaign data to JSON or CSV

### 🔍 User Claims Status
- Check if users have required proofs for claiming rewards
- Period-by-period breakdown of claim eligibility
- Identify missing proofs (block headers, point data, user slopes)
- Export detailed claim status reports

### 🔐 Proof Generator
- Generate user voting proofs for reward claims
- Generate gauge proofs for voting weight verification
- Retrieve block information for proof anchoring
- Download generated proofs in JSON format

### 📈 Analytics Dashboard
- View current market snapshots with $/vote metrics
- Access historical round data and metadata
- Analyze gauge-specific historical performance
- Export analytics data for further analysis

## Installation

### Prerequisites
- Python 3.10 or higher
- UV or pip

### Setup

```bash
# Clone and install
git clone https://github.com/stake-dao/votemarket-proof-toolkit
cd votemarket-proof-toolkit

# With UV (recommended)
uv sync

# With pip
pip install -e .
```

3. **Configure RPC endpoints** (required):

   Set environment variables for the chains you want to use:
   ```bash
   export RPC_URL_1="https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY"        # Ethereum
   export RPC_URL_42161="https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY"    # Arbitrum
   export RPC_URL_10="https://opt-mainnet.g.alchemy.com/v2/YOUR_KEY"       # Optimism
   export RPC_URL_137="https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY"  # Polygon
   export RPC_URL_8453="https://base-mainnet.g.alchemy.com/v2/YOUR_KEY"    # Base
   ```

   Or create a `.env` file in the toolkit root directory:
   ```env
   RPC_URL_1=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
   RPC_URL_42161=https://arb-mainnet.g.alchemy.com/v2/YOUR_KEY
   # ... etc
   ```

## Usage

### Running the UI

```bash
# With UV (from project root)
uv run streamlit run streamlit_ui/app.py

# With pip
streamlit run streamlit_ui/app.py

# Or use the convenience script
cd streamlit_ui && ./run.sh
```

The UI will open at `http://localhost:8501`

### Quick Start Guide

1. **Explore Active Campaigns**
   - Navigate to "Active Campaigns" page
   - Select a protocol (e.g., Curve, Balancer)
   - Choose a chain (e.g., Arbitrum, Ethereum)
   - Enable "Check Proof Status" to verify oracle data
   - Click "Load Campaigns"

2. **Check User Claims**
   - Go to "User Claims" page
   - Enter a user's wallet address
   - Select protocol, chain, and campaign ID
   - Click "Check Claim Status"
   - Review which periods are claimable

3. **Generate Proofs**
   - Visit "Proof Generator" page
   - Choose proof type (User, Gauge, or Block Info)
   - Fill in required parameters
   - Click generate and download the proof

4. **View Analytics**
   - Access "Analytics Dashboard"
   - Load market snapshots for $/vote metrics
   - Explore historical round data
   - Analyze gauge-specific trends

## Configuration

### Streamlit Settings

The UI uses custom settings in `.streamlit/config.toml`:
- Theme colors matching VoteMarket branding
- Server configuration for localhost access
- Browser settings for local development

You can customize these settings by editing the config file.

### Cache Settings

The toolkit uses built-in caching for:
- RPC responses (TTL: varies by data type)
- Registry data (fetched from GitHub)
- Token information and prices

Cache files are stored in the toolkit's cache directory.

## Supported Protocols

- **Curve** - Curve Finance gauge voting
- **Balancer** - Balancer protocol gauge voting
- **Frax** - Frax Finance gauge voting
- **FXN** - f(x) Protocol gauge voting
- **Pendle** - Pendle Finance gauge voting

## Supported Chains

- **Ethereum** (Chain ID: 1)
- **Optimism** (Chain ID: 10)
- **Polygon** (Chain ID: 137)
- **Base** (Chain ID: 8453)
- **Arbitrum** (Chain ID: 42161)

## Project Structure

```
streamlit_ui/
├── app.py                      # Main application entry point
├── pages/                      # Streamlit pages
│   ├── 1_Active_Campaigns.py   # Campaign browser
│   ├── 2_User_Claims.py        # Claim status checker
│   ├── 3_Proof_Generator.py    # Proof generation tools
│   └── 4_Analytics_Dashboard.py # Analytics and metrics
├── utils/                      # Utility functions
│   ├── __init__.py
│   └── helpers.py              # UI helper functions
├── .streamlit/                 # Streamlit configuration
│   └── config.toml
├── requirements.txt            # UI-specific dependencies
└── README.md                   # This file
```

## Troubleshooting

### Common Issues

**RPC Connection Errors**
- Ensure RPC URLs are set as environment variables
- Verify your RPC provider API keys are valid
- Check network connectivity

**Module Import Errors**
- With UV: Make sure dependencies are synced: `uv pip sync`
- With pip: Make sure the base toolkit is installed: `pip install -e ..`
- Verify you're running from the correct directory

**Data Loading Issues**
- Check that the protocol/chain combination is supported
- Verify the campaign ID exists
- Ensure addresses are valid Ethereum addresses (0x...)

**Cache Issues**
- Clear Streamlit cache: Press `C` in the running app
- Delete cache files: Remove `~/.votemarket_toolkit_cache/`

### Performance Tips

1. **Enable Proof Checking Selectively**: Checking proofs adds extra RPC calls. Disable when not needed.
2. **Use Specific Campaign IDs**: Loading specific campaigns is faster than loading all campaigns.
3. **Export Large Datasets**: For bulk analysis, export to JSON/CSV and use external tools.

## Development

### Adding New Features

1. **New Page**: Create a file in `pages/` following the naming convention `N_Page_Name.py`
2. **New Utility**: Add functions to `utils/helpers.py`
3. **Custom Styling**: Update CSS in `app.py` or page files

### Testing

Test the UI with different protocols and chains:

```bash
# With UV (from project root)
uv run streamlit run streamlit_ui/app.py

# With pip (from streamlit_ui directory)
streamlit run app.py
```

Navigate through all pages and verify:
- Data loads correctly
- Exports work
- Error handling is graceful
- UI is responsive

## Resources

- [VoteMarket Toolkit Documentation](https://github.com/stake-dao/votemarket-proof-toolkit)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [VoteMarket Analytics](https://github.com/stake-dao/votemarket-analytics)
- [Stake DAO](https://stakedao.org/)

## License

AGPL-3.0 - Same as the VoteMarket Proof Toolkit

## Support

For issues or questions:
- Open an issue on the [GitHub repository](https://github.com/stake-dao/votemarket-proof-toolkit)
- Contact the Stake DAO team

---

**Built with Streamlit** | **Powered by VoteMarket Proof Toolkit v1.0.6**
