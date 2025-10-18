"""
User Eligibility Check - Streamlit Page

This page allows users to check their eligibility for VoteMarket rewards
across all campaigns and protocols.
"""

import asyncio
from datetime import datetime
import streamlit as st
import pandas as pd
from eth_utils.address import is_address, to_checksum_address

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from votemarket_toolkit.proofs.user_eligibility_service import UserEligibilityService
from votemarket_toolkit.shared import registry


# Page configuration
st.set_page_config(
    page_title="User Eligibility Check - VoteMarket",
    page_icon="✅",
    layout="wide"
)

# Initialize session state
if "eligibility_results" not in st.session_state:
    st.session_state.eligibility_results = None
if "last_user_address" not in st.session_state:
    st.session_state.last_user_address = None


async def check_user_eligibility(
    user: str,
    protocol: str,
    chain_id: int | None = None,
    gauge_address: str | None = None,
    status_filter: str = "all"
):
    """Check user eligibility using the service."""
    service = UserEligibilityService()
    try:
        results = await service.check_user_eligibility(
            user=user,
            protocol=protocol,
            chain_id=chain_id,
            gauge_address=gauge_address,
            status_filter=status_filter
        )
        return results
    finally:
        await service.close()


def format_campaign_data(campaign_data):
    """Format campaign data for display."""
    periods_df = pd.DataFrame(campaign_data['periods'])
    
    # Format epoch timestamps
    if not periods_df.empty:
        periods_df['epoch_date'] = pd.to_datetime(periods_df['epoch'], unit='s', utc=True)
        periods_df['epoch_formatted'] = periods_df['epoch_date'].dt.strftime('%Y-%m-%d %H:%M UTC')
        
        # Add visual indicators
        periods_df['has_proof_icon'] = periods_df['has_proof'].apply(lambda x: '✅' if x else '❌')
        periods_df['claimable_icon'] = periods_df['claimable'].apply(lambda x: '✅' if x else '❌')
        
    return periods_df


def main():
    st.title("🔍 User Eligibility Check")
    st.markdown("Check your eligibility for VoteMarket rewards across all campaigns")
    
    # Create input columns
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        user_address = st.text_input(
            "User Address",
            placeholder="0x...",
            help="Enter your Ethereum address to check eligibility"
        )
        
    with col2:
        protocol = st.selectbox(
            "Protocol",
            ["curve", "balancer", "fxn", "pendle"],
            help="Select the protocol to check"
        )
        
    with col3:
        chain_id = st.selectbox(
            "Chain",
            [
                ("All Chains", None),
                ("Ethereum", 1),
                ("Optimism", 10),
                ("Polygon", 137),
                ("Base", 8453),
                ("Arbitrum", 42161)
            ],
            format_func=lambda x: x[0],
            index=0
        )
    
    # Advanced filters (collapsible)
    with st.expander("Advanced Filters"):
        col_adv1, col_adv2 = st.columns(2)
        
        with col_adv1:
            gauge_address = st.text_input(
                "Specific Gauge (Optional)",
                placeholder="0x...",
                help="Filter by specific gauge address"
            )
            
        with col_adv2:
            status_filter = st.selectbox(
                "Campaign Status",
                [
                    ("All", "all"),
                    ("Active Only", "active"),
                    ("Closed Only", "closed")
                ],
                format_func=lambda x: x[0],
                index=0
            )
    
    # Check button
    if st.button("Check Eligibility", type="primary", use_container_width=True):
        # Validate inputs
        if not user_address:
            st.error("Please enter a user address")
            return
            
        if not is_address(user_address):
            st.error("Invalid Ethereum address")
            return
            
        if gauge_address and not is_address(gauge_address):
            st.error("Invalid gauge address")
            return
        
        # Show loading spinner
        with st.spinner(f"Checking eligibility for {user_address[:10]}..."):
            try:
                # Run async function
                results = asyncio.run(check_user_eligibility(
                    user=user_address,
                    protocol=protocol,
                    chain_id=chain_id[1] if chain_id[1] else None,
                    gauge_address=gauge_address if gauge_address else None,
                    status_filter=status_filter[1]
                ))
                
                st.session_state.eligibility_results = results
                st.session_state.last_user_address = user_address
                
            except Exception as e:
                st.error(f"Error checking eligibility: {str(e)}")
                return
    
    # Display results
    if st.session_state.eligibility_results:
        results = st.session_state.eligibility_results
        
        # Summary section
        st.markdown("---")
        st.subheader("📊 Summary")
        
        summary_cols = st.columns(4)
        with summary_cols[0]:
            st.metric("Total Campaigns Checked", results['summary']['total_campaigns_checked'])
        with summary_cols[1]:
            st.metric("Campaigns with Eligibility", results['summary']['campaigns_with_eligibility'])
        with summary_cols[2]:
            st.metric("Claimable Periods", results['summary']['total_claimable_periods'])
        with summary_cols[3]:
            st.metric("Protocol", results['protocol'].upper())
        
        # Chain breakdown
        if results['summary']['chains']:
            st.markdown("### Chain Breakdown")
            chain_df = pd.DataFrame.from_dict(results['summary']['chains'], orient='index')
            chain_df.index.name = 'Chain'
            chain_df = chain_df.reset_index()
            
            # Create a nice table
            chain_cols = st.columns(len(chain_df))
            for idx, (_, row) in enumerate(chain_df.iterrows()):
                with chain_cols[idx]:
                    st.markdown(f"**{row['Chain']}**")
                    st.caption(f"Campaigns: {row['total_campaigns']}")
                    st.caption(f"Eligible: {row['eligible_campaigns']}")
                    st.caption(f"Claimable: {row['claimable_periods']}")
        
        # Detailed campaign results
        st.markdown("---")
        st.subheader("🎯 Campaign Details")
        
        # Group by chain
        for chain_id, chain_data in results['chains'].items():
            if not chain_data['campaigns']:
                continue
                
            chain_name = {
                1: "Ethereum",
                10: "Optimism", 
                137: "Polygon",
                8453: "Base",
                42161: "Arbitrum"
            }.get(chain_id, f"Chain {chain_id}")
            
            st.markdown(f"### {chain_name}")
            
            # Display each campaign
            for campaign in chain_data['campaigns']:
                with st.expander(
                    f"Campaign #{campaign['id']} - Gauge: {campaign['gauge'][:10]}... "
                    f"{'✅ Eligible' if campaign['summary']['has_eligibility'] else '❌ No Eligibility'}"
                ):
                    # Campaign info
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.markdown(f"**Manager:** `{campaign['manager'][:20]}...`")
                    with col_info2:
                        st.markdown(f"**Reward Token:** `{campaign['reward_token'][:20]}...`")
                    with col_info3:
                        st.markdown(f"**Status:** {'🔴 Closed' if campaign['is_closed'] else '🟢 Active'}")
                    
                    # Summary metrics
                    st.markdown("**Summary:**")
                    metric_cols = st.columns(3)
                    with metric_cols[0]:
                        st.metric("Total Periods", campaign['summary']['total_periods'])
                    with metric_cols[1]:
                        st.metric("Claimable", campaign['summary']['claimable_periods'])
                    with metric_cols[2]:
                        st.metric("Has Eligibility", "Yes" if campaign['summary']['has_eligibility'] else "No")
                    
                    # Period details
                    if campaign['periods']:
                        st.markdown("**Period Details:**")
                        periods_df = format_campaign_data(campaign)
                        
                        # Display table
                        display_cols = ['period', 'epoch_formatted', 'status', 'has_proof_icon', 'claimable_icon', 'reason']
                        display_names = {
                            'period': 'Period',
                            'epoch_formatted': 'Epoch Date',
                            'status': 'Status',
                            'has_proof_icon': 'Has Proof',
                            'claimable_icon': 'Claimable',
                            'reason': 'Notes'
                        }
                        
                        st.dataframe(
                            periods_df[display_cols].rename(columns=display_names),
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Copy addresses button
                        if campaign['summary']['claimable_periods'] > 0:
                            st.markdown("**📋 Quick Copy:**")
                            copy_cols = st.columns(3)
                            with copy_cols[0]:
                                st.code(campaign['gauge'], language="text")
                                st.caption("Gauge Address")
                            with copy_cols[1]:
                                st.code(st.session_state.last_user_address, language="text")
                                st.caption("User Address")
                            with copy_cols[2]:
                                st.code(results['protocol'], language="text")
                                st.caption("Protocol")
        
        # Instructions section
        if results['summary']['total_claimable_periods'] > 0:
            st.markdown("---")
            st.info(
                "🎉 **You have claimable rewards!**\n\n"
                "To claim your rewards:\n"
                "1. Go to the Proof Generator page\n"
                "2. Generate proofs for the claimable periods\n"
                "3. Use the proofs to claim your rewards on-chain\n\n"
                "Or download pre-generated proofs from: "
                "[VoteMarket API](https://github.com/stake-dao/api/tree/main/api/votemarket)"
            )
        else:
            st.info(
                "ℹ️ **No claimable rewards found**\n\n"
                "This could mean:\n"
                "- You haven't voted in any campaigns\n"
                "- Your votes haven't been processed yet\n"
                "- The proofs aren't available yet\n\n"
                "Check back later or try a different protocol/chain."
            )


if __name__ == "__main__":
    main()