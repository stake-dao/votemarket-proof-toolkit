"""
User Claims Status Page
Check user eligibility for claiming campaign rewards
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
from votemarket_toolkit.shared.registry import get_platform

st.set_page_config(page_title="User Claims", page_icon="🔍", layout="wide")

st.title("🔍 User Claims Status")
st.markdown("Check user eligibility and proof status for claiming campaign rewards")

# Input form
st.markdown("### Enter Details")

col1, col2 = st.columns(2)

with col1:
    user_address = st.text_input(
        "User Address",
        placeholder="0x...",
        help="Ethereum address of the user to check"
    )

    protocol = st.selectbox(
        "Protocol",
        options=["curve", "balancer", "frax", "fxn", "pendle"],
        index=0
    )

with col2:
    campaign_id = st.number_input(
        "Campaign ID",
        min_value=0,
        value=0,
        step=1,
        help="The campaign ID to check"
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

# Optional: Platform address override
with st.expander("⚙️ Advanced Options"):
    custom_platform = st.text_input(
        "Platform Address (optional)",
        placeholder="Leave empty to use default from registry",
        help="Override the platform address instead of using registry"
    )

st.markdown("---")

# Check button
if st.button("🔍 Check Claim Status", type="primary", use_container_width=True):

    # Validation
    if not user_address:
        st.error("Please enter a user address")
    elif not user_address.startswith("0x") or len(user_address) != 42:
        st.error("Invalid Ethereum address format")
    elif campaign_id < 0:
        st.error("Campaign ID must be a positive number")
    else:
        with st.spinner(f"Checking claim status for user {user_address[:6]}...{user_address[-4:]}..."):
            try:
                service = CampaignService()

                # Get platform address
                if custom_platform and custom_platform.strip():
                    platform_address = custom_platform.strip()
                    st.info(f"Using custom platform address: `{platform_address}`")
                else:
                    # Try v2 first, then v2_old, then v1
                    platform_address = get_platform(protocol, chain_id, "v2")
                    if not platform_address:
                        platform_address = get_platform(protocol, chain_id, "v2_old")
                    if not platform_address:
                        platform_address = get_platform(protocol, chain_id, "v1")

                    if not platform_address:
                        st.error(f"No platform found for {protocol} on {chain_name}. Please use a custom platform address.")
                        st.stop()

                    st.info(f"Using platform address from registry: `{platform_address}`")

                # First, fetch the campaign
                campaigns = asyncio.run(service.get_campaigns(
                    chain_id=chain_id,
                    platform_address=platform_address,
                    campaign_id=campaign_id,
                    check_proofs=False
                ))

                if not campaigns:
                    st.error(f"Campaign #{campaign_id} not found on {chain_name}")
                else:
                    campaign = campaigns[0]

                    # Display campaign info
                    st.success(f"✅ Found Campaign #{campaign_id}")

                    info_col1, info_col2, info_col3 = st.columns(3)

                    with info_col1:
                        st.metric("Campaign ID", campaign['id'])

                    with info_col2:
                        token_symbol = campaign.get('reward_token', {}).get('symbol', 'Unknown')
                        st.metric("Reward Token", token_symbol)

                    with info_col3:
                        remaining = campaign.get('remaining_periods', 0)
                        st.metric("Remaining Periods", remaining)

                    st.markdown("---")

                    # Check user claim status
                    with st.spinner("Checking proof status..."):
                        claim_status = asyncio.run(service.get_user_campaign_proof_status(
                            chain_id=chain_id,
                            platform_address=platform_address,
                            campaign=campaign,
                            user_address=user_address
                        ))

                        # Display results
                        st.markdown("### 📊 Claim Status Results")

                        # Get periods from the response
                        periods = claim_status.get('periods', [])

                        # Overall status
                        all_claimable = all(period['is_claimable'] for period in periods)

                        if all_claimable:
                            st.success("🎉 User can claim rewards for ALL periods!")
                        else:
                            claimable_count = sum(1 for p in periods if p['is_claimable'])
                            total_count = len(periods)
                            st.warning(f"⚠️ User can claim {claimable_count}/{total_count} periods")

                        st.markdown("---")

                        # Period-by-period breakdown
                        st.markdown("### Period Breakdown")

                        # Create detailed table
                        period_data = []
                        for idx, period in enumerate(periods):
                            period_data.append({
                                'Period': idx + 1,
                                'Timestamp': datetime.fromtimestamp(period['timestamp']).strftime('%Y-%m-%d %H:%M'),
                                'Can Claim': '✅ Yes' if period['is_claimable'] else '❌ No',
                                'Block Updated': '✅' if period['block_updated'] else '❌',
                                'Point Data': '✅' if period['point_data_inserted'] else '❌',
                                'User Slope': '✅' if period['user_slope_inserted'] else '❌',
                            })

                        df = pd.DataFrame(period_data)

                        # Style the dataframe
                        def highlight_claimable(row):
                            if '✅ Yes' in row['Can Claim']:
                                return ['background-color: #d4edda'] * len(row)
                            else:
                                return ['background-color: #f8d7da'] * len(row)

                        styled_df = df.style.apply(highlight_claimable, axis=1)
                        st.dataframe(styled_df, use_container_width=True, hide_index=True)

                        # Detailed proof status
                        st.markdown("---")
                        st.markdown("### 🔐 Proof Status Details")

                        st.markdown("""
                        For a user to claim rewards for a period, three conditions must be met:
                        - **Block Updated**: The block header for the period must be inserted into the oracle
                        - **Point Data**: The gauge point data (voting weight) must be inserted
                        - **User Slope**: The user's vote slope data must be inserted

                        All three must be ✅ for claiming to be possible.
                        """)

                        # Show periods with issues
                        problematic_periods = [p for p in periods if not p['is_claimable']]

                        if problematic_periods:
                            st.markdown("#### ⚠️ Periods with Missing Proofs")

                            for idx, period in enumerate(problematic_periods):
                                with st.expander(f"Period {periods.index(period) + 1} - {datetime.fromtimestamp(period['timestamp']).strftime('%Y-%m-%d')}"):
                                    missing = []
                                    if not period['block_updated']:
                                        missing.append("❌ Block header not inserted")
                                    if not period['point_data_inserted']:
                                        missing.append("❌ Gauge point data not inserted")
                                    if not period['user_slope_inserted']:
                                        missing.append("❌ User vote slope not inserted")

                                    st.markdown("**Missing Proofs:**")
                                    for m in missing:
                                        st.write(m)

                                    st.info("These proofs need to be generated and submitted to the oracle before claiming is possible.")

                        # Export results
                        st.markdown("---")
                        st.markdown("### 📥 Export Results")

                        import json
                        export_data = {
                            'user_address': user_address,
                            'campaign_id': campaign_id,
                            'chain_id': chain_id,
                            'protocol': protocol,
                            'platform_address': platform_address,
                            'checked_at': datetime.now().isoformat(),
                            'claim_status': claim_status,
                            'campaign_info': {
                                'id': campaign['id'],
                                'gauge': campaign.get('campaign', {}).get('gauge'),
                                'reward_token': campaign.get('reward_token', {}).get('symbol'),
                            }
                        }

                        json_data = json.dumps(export_data, indent=2)

                        st.download_button(
                            label="📥 Download Full Report (JSON)",
                            data=json_data,
                            file_name=f"claim_status_{user_address[:8]}_{campaign_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )

            except Exception as e:
                st.error(f"Error checking claim status: {str(e)}")
                import traceback
                with st.expander("View Error Details"):
                    st.code(traceback.format_exc())

# Info section
st.markdown("---")
st.markdown("### ℹ️ How It Works")

st.markdown("""
This tool checks whether a user has the necessary cryptographic proofs inserted into the VoteMarket oracle
to claim rewards for a specific campaign.

**Steps:**
1. Enter the user's wallet address
2. Select the protocol and chain
3. Enter the campaign ID you want to check
4. Click "Check Claim Status"

**Understanding Results:**
- **Green (✅)**: User can claim for this period
- **Red (❌)**: Missing proofs prevent claiming

**What to do if proofs are missing:**
- Use the "Proof Generator" page to create the required proofs
- Submit proofs to the oracle contract
- Come back here to verify the proofs are inserted
""")
