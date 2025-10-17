"""
Active Campaigns Page
Browse and analyze active voting campaigns
"""

import streamlit as st
import asyncio
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path to import toolkit
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from votemarket_toolkit.campaigns import CampaignService
from votemarket_toolkit.shared.registry import get_all_platforms

st.set_page_config(page_title="Active Campaigns", page_icon="📊", layout="wide")

st.title("📊 Active Campaigns")
st.markdown("Browse active voting campaigns across chains and protocols")

# Sidebar filters
with st.sidebar:
    st.header("Filters")

    protocol = st.selectbox(
        "Protocol",
        options=["curve", "balancer", "frax", "fxn", "pendle"],
        index=0
    )

    chain_options = {
        "Ethereum": 1,
        "Optimism": 10,
        "Polygon": 137,
        "Base": 8453,
        "Arbitrum": 42161
    }

    chain_name = st.selectbox(
        "Chain",
        options=list(chain_options.keys()),
        index=4  # Default to Arbitrum
    )
    chain_id = chain_options[chain_name]

    check_proofs = st.checkbox(
        "Check Proof Status",
        value=True,
        help="Verify if block headers and point data are inserted in oracle"
    )

    st.markdown("---")

    # Export options
    st.subheader("Export Options")
    export_format = st.radio(
        "Format",
        options=["JSON", "CSV"],
        index=0
    )

# Main content
col1, col2 = st.columns([3, 1])

with col2:
    if st.button("🔄 Load Campaigns", type="primary", use_container_width=True):
        st.session_state.load_campaigns = True

# Initialize session state
if 'campaigns_data' not in st.session_state:
    st.session_state.campaigns_data = None
if 'load_campaigns' not in st.session_state:
    st.session_state.load_campaigns = False

# Load campaigns
if st.session_state.load_campaigns:
    st.session_state.load_campaigns = False  # Reset flag

    with st.spinner(f"Loading active campaigns for {protocol} on {chain_name}..."):
        try:
            service = CampaignService()

            # Run async function
            campaigns = asyncio.run(service.get_active_campaigns_by_protocol(
                protocol=protocol,
                chain_id=chain_id,
                check_proofs=check_proofs
            ))

            st.session_state.campaigns_data = campaigns
            st.success(f"✅ Loaded {len(campaigns)} active campaign(s)")

        except Exception as e:
            st.error(f"Error loading campaigns: {str(e)}")
            st.session_state.campaigns_data = None

# Display campaigns
if st.session_state.campaigns_data:
    campaigns = st.session_state.campaigns_data

    # Summary metrics
    st.markdown("### Campaign Summary")

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric("Total Campaigns", len(campaigns))

    with metric_col2:
        total_periods = sum(c.get('remaining_periods', 0) for c in campaigns)
        st.metric("Total Remaining Periods", total_periods)

    with metric_col3:
        active_count = sum(1 for c in campaigns if c.get('status_info', {}).get('status') == 'ACTIVE')
        st.metric("Active Status", active_count)

    with metric_col4:
        if campaigns and 'reward_token' in campaigns[0]:
            total_value = sum(
                c.get('campaign', {}).get('total_reward_amount', 0) *
                c.get('reward_token', {}).get('price', 0) /
                10**c.get('reward_token', {}).get('decimals', 18)
                for c in campaigns if 'reward_token' in c
            )
            st.metric("Total Value (USD)", f"${total_value:,.2f}")

    st.markdown("---")

    # Campaign cards
    for idx, campaign in enumerate(campaigns):
        with st.expander(f"🎯 Campaign #{campaign['id']} - {campaign.get('reward_token', {}).get('symbol', 'Unknown')}"):

            # Campaign details in columns
            detail_col1, detail_col2 = st.columns(2)

            with detail_col1:
                st.markdown("#### Campaign Info")
                campaign_data = campaign.get('campaign', {})

                st.write(f"**Gauge:** `{campaign_data.get('gauge', 'N/A')}`")
                st.write(f"**Manager:** `{campaign_data.get('manager', 'N/A')}`")
                st.write(f"**Reward Token:** `{campaign_data.get('reward_token', 'N/A')}`")

                if 'reward_token' in campaign:
                    token_info = campaign['reward_token']
                    st.write(f"**Token Symbol:** {token_info.get('symbol', 'N/A')}")
                    st.write(f"**Token Name:** {token_info.get('name', 'N/A')}")
                    st.write(f"**Token Price:** ${token_info.get('price', 0):.4f}")

                total_reward = campaign_data.get('total_reward_amount', 0)
                decimals = campaign.get('reward_token', {}).get('decimals', 18)
                formatted_reward = total_reward / 10**decimals

                st.write(f"**Total Reward:** {formatted_reward:,.4f}")

                if 'reward_token' in campaign:
                    usd_value = formatted_reward * campaign['reward_token'].get('price', 0)
                    st.write(f"**USD Value:** ${usd_value:,.2f}")

            with detail_col2:
                st.markdown("#### Status Info")

                status_info = campaign.get('status_info', {})
                status = status_info.get('status', 'UNKNOWN')

                # Color code the status
                status_color = {
                    'ACTIVE': '🟢',
                    'CLOSED': '🔴',
                    'CLOSABLE_BY_MANAGER': '🟡',
                    'CLOSABLE_BY_ANYONE': '🟠'
                }.get(status, '⚪')

                st.write(f"**Status:** {status_color} {status}")
                st.write(f"**Can Close:** {'Yes' if status_info.get('can_close') else 'No'}")
                st.write(f"**Who Can Close:** {status_info.get('who_can_close', 'N/A')}")

                if status_info.get('days_until_public_close'):
                    st.write(f"**Days Until Public Close:** {status_info.get('days_until_public_close')}")

                st.write(f"**Remaining Periods:** {campaign.get('remaining_periods', 0)}")
                st.write(f"**Number of Periods:** {campaign_data.get('number_of_periods', 0)}")
                st.write(f"**Is Closed:** {'Yes' if campaign.get('is_closed') else 'No'}")
                st.write(f"**Whitelist Only:** {'Yes' if campaign.get('is_whitelist_only') else 'No'}")

            # Periods table
            if 'periods' in campaign and campaign['periods']:
                st.markdown("#### Period Details")

                periods_data = []
                for period in campaign['periods']:
                    period_reward = period.get('reward_per_period', 0) / 10**decimals

                    periods_data.append({
                        'Timestamp': datetime.fromtimestamp(period.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M'),
                        'Reward/Period': f"{period_reward:,.4f}",
                        'Reward/Vote': period.get('reward_per_vote', 0),
                        'Leftover': period.get('leftover', 0),
                        'Updated': '✅' if period.get('updated') else '❌',
                        'Block Updated': '✅' if period.get('block_updated') else '❌',
                        'Point Data': '✅' if period.get('point_data_inserted') else '❌',
                    })

                df = pd.DataFrame(periods_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

            # Whitelist addresses
            if campaign.get('is_whitelist_only') and campaign.get('addresses'):
                st.markdown("#### Whitelisted Addresses")
                for addr in campaign['addresses']:
                    st.code(addr, language=None)

    # Export functionality
    st.markdown("---")
    st.markdown("### Export Data")

    export_col1, export_col2 = st.columns([3, 1])

    with export_col1:
        if export_format == "JSON":
            import json
            json_data = json.dumps(campaigns, indent=2)
            st.download_button(
                label="📥 Download JSON",
                data=json_data,
                file_name=f"campaigns_{protocol}_{chain_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        else:  # CSV
            # Flatten campaigns for CSV
            csv_data = []
            for c in campaigns:
                campaign_info = c.get('campaign', {})
                csv_data.append({
                    'ID': c['id'],
                    'Gauge': campaign_info.get('gauge', ''),
                    'Manager': campaign_info.get('manager', ''),
                    'Reward Token': campaign_info.get('reward_token', ''),
                    'Token Symbol': c.get('reward_token', {}).get('symbol', ''),
                    'Total Reward': campaign_info.get('total_reward_amount', 0),
                    'Status': c.get('status_info', {}).get('status', ''),
                    'Remaining Periods': c.get('remaining_periods', 0),
                    'Is Closed': c.get('is_closed', False),
                })

            df_export = pd.DataFrame(csv_data)
            csv_string = df_export.to_csv(index=False)

            st.download_button(
                label="📥 Download CSV",
                data=csv_string,
                file_name=f"campaigns_{protocol}_{chain_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

else:
    st.info("👆 Click 'Load Campaigns' to view active campaigns")

    st.markdown("""
    ### How to use:

    1. **Select Protocol** - Choose from Curve, Balancer, Frax, FXN, or Pendle
    2. **Select Chain** - Pick the blockchain network
    3. **Check Proof Status** - Enable to verify oracle data insertion
    4. **Click Load** - Fetch active campaigns
    5. **Export** - Download campaign data as JSON or CSV

    The tool will display detailed information including:
    - Campaign status and reward details
    - Token information and USD values
    - Period-by-period breakdown
    - Proof insertion status for claiming
    """)
