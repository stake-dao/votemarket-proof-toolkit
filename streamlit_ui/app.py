"""
VoteMarket Toolkit - Unified Dashboard

A single page application for checking user eligibility, generating proofs,
and viewing campaign status across all VoteMarket protocols.
"""

import asyncio
from datetime import datetime
import streamlit as st
import pandas as pd
from eth_utils.address import is_address, to_checksum_address

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from votemarket_toolkit.proofs.user_eligibility_service import UserEligibilityService
from votemarket_toolkit.campaigns.service import CampaignService
from votemarket_toolkit.shared import registry


# Page configuration
st.set_page_config(
    page_title="VoteMarket Toolkit",
    page_icon="🗳️",
    layout="wide"
)


# Initialize session state
if "user_address" not in st.session_state:
    st.session_state.user_address = ""
if "eligibility_results" not in st.session_state:
    st.session_state.eligibility_results = None
if "selected_campaign" not in st.session_state:
    st.session_state.selected_campaign = None


async def check_user_eligibility(user: str, protocol: str, chain_id: int = None):
    """Check user eligibility using the service."""
    service = UserEligibilityService()
    try:
        results = await service.check_user_eligibility(
            user=user,
            protocol=protocol,
            chain_id=chain_id,
            status_filter="all"
        )
        return results
    finally:
        await service.close()


def show_proof_command(user: str, gauge: str, protocol: str, epoch: int):
    """Show command to generate proof."""
    # For simplicity, we'll show the command to run
    return {
        'command': f'make user-proof USER={user} GAUGE={gauge} PROTOCOL={protocol} BLOCK=<block_at_epoch>',
        'note': f'You need to find the block number at epoch {epoch}'
    }


async def get_all_campaigns(protocol: str, chain_id: int = None):
    """Get all campaigns across platforms."""
    service = CampaignService()
    all_campaigns = []
    
    # Get platforms
    platforms = registry.get_all_platforms(protocol)
    if chain_id:
        platforms = [p for p in platforms if p["chain_id"] == chain_id]
    
    for platform in platforms:
        try:
            campaigns = await service.get_campaigns(
                chain_id=platform["chain_id"],
                platform_address=platform["address"],
                active_only=False
            )
            
            for campaign in campaigns:
                campaign['platform_chain_id'] = platform["chain_id"]
                campaign['platform_address'] = platform["address"]
                all_campaigns.append(campaign)
        except:
            continue
            
    return all_campaigns


def main():
    # Header
    st.title("🗳️ VoteMarket Toolkit")
    st.markdown("Check eligibility, generate proofs, and manage your VoteMarket rewards")
    
    # Main input section
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        user_address = st.text_input(
            "User Address",
            value=st.session_state.user_address,
            placeholder="0x...",
            help="Enter your Ethereum address"
        )
        
    with col2:
        protocol = st.selectbox(
            "Protocol",
            ["curve", "balancer", "fxn", "pendle"],
            help="Select the protocol"
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
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        check_eligibility_btn = st.button(
            "🔍 Check My Eligibility",
            type="primary",
            use_container_width=True,
            disabled=not user_address
        )
    
    with col2:
        view_all_campaigns_btn = st.button(
            "📊 View All Campaigns",
            use_container_width=True
        )
    
    with col3:
        st.empty()  # Spacer
    
    # Validation
    if user_address and not is_address(user_address):
        st.error("Invalid Ethereum address")
        return
    
    # Process user eligibility check
    if check_eligibility_btn and user_address:
        st.session_state.user_address = user_address
        
        with st.spinner(f"Checking eligibility for {user_address[:10]}..."):
            try:
                results = asyncio.run(check_user_eligibility(
                    user=user_address,
                    protocol=protocol,
                    chain_id=chain_id[1] if chain_id[1] else None
                ))
                st.session_state.eligibility_results = results
            except Exception as e:
                st.error(f"Error: {str(e)}")
                return
    
    # Display user eligibility results
    if st.session_state.eligibility_results:
        results = st.session_state.eligibility_results
        
        st.markdown("---")
        
        # Summary metrics
        st.subheader("📊 Your Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Campaigns", results['summary']['total_campaigns_checked'])
        with col2:
            st.metric("With Your Votes", results['summary']['campaigns_with_eligibility'])
        with col3:
            st.metric("Claimable Periods", results['summary']['total_claimable_periods'])
        with col4:
            st.metric("Protocol", results['protocol'].upper())
        
        if results['summary']['campaigns_with_eligibility'] > 0:
            st.markdown("---")
            st.subheader("🎯 Your Claimable Campaigns")
            
            # Display campaigns by chain
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
                        f"Campaign #{campaign['id']} - {campaign['gauge'][:10]}... "
                        f"({campaign['summary']['claimable_periods']} claimable periods)"
                    ):
                        # Campaign info
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown(f"**Manager:** `{campaign['manager']}`")
                        with col2:
                            st.markdown(f"**Reward Token:** `{campaign['reward_token']}`")
                        with col3:
                            st.markdown(f"**Status:** {'🔴 Closed' if campaign['is_closed'] else '🟢 Active'}")
                        
                        # Period details with proof generation
                        st.markdown("**Periods:**")
                        
                        # Create dataframe for periods
                        periods_df = pd.DataFrame(campaign['periods'])
                        periods_df['epoch_date'] = pd.to_datetime(periods_df['epoch'], unit='s', utc=True)
                        periods_df['epoch_formatted'] = periods_df['epoch_date'].dt.strftime('%Y-%m-%d %H:%M UTC')
                        
                        # Display periods with action buttons
                        for _, period in periods_df.iterrows():
                            col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 2])
                            
                            with col1:
                                st.markdown(f"#{period['period']}")
                            
                            with col2:
                                st.markdown(period['epoch_formatted'])
                            
                            with col3:
                                if period['has_proof']:
                                    st.success("✅ Has Proof")
                                else:
                                    st.warning("❌ No Proof")
                            
                            with col4:
                                st.markdown(period['status'])
                            
                            with col5:
                                if period['claimable']:
                                    if st.button(
                                        "📥 Download Proof",
                                        key=f"download_{campaign['id']}_{period['period']}",
                                        use_container_width=True
                                    ):
                                        # TODO: Implement proof download from GitHub
                                        st.info("Proof download coming soon!")
                                elif period['status'] == 'Ended' and not period['has_proof']:
                                    if st.button(
                                        "⚡ Generate Proof",
                                        key=f"generate_{campaign['id']}_{period['period']}",
                                        use_container_width=True,
                                        type="secondary"
                                    ):
                                        proof_info = show_proof_command(
                                            user=results['user'],
                                            gauge=campaign['gauge'],
                                            protocol=results['protocol'],
                                            epoch=int(period['epoch'])
                                        )
                                        st.info(f"To generate proof, run:\n```\n{proof_info['command']}\n```\n{proof_info['note']}")
        else:
            st.info("No campaigns found where you have claimable rewards.")
    
    # View all campaigns
    if view_all_campaigns_btn:
        st.markdown("---")
        st.subheader("📊 All Campaigns")
        
        with st.spinner("Loading all campaigns..."):
            try:
                all_campaigns = asyncio.run(get_all_campaigns(
                    protocol=protocol,
                    chain_id=chain_id[1] if chain_id[1] else None
                ))
                
                if all_campaigns:
                    # Create summary
                    total_campaigns = len(all_campaigns)
                    active_campaigns = sum(1 for c in all_campaigns if not c['is_closed'])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Total Campaigns", total_campaigns)
                    with col2:
                        st.metric("Active Campaigns", active_campaigns)
                    
                    # Create dataframe
                    campaigns_data = []
                    for c in all_campaigns:
                        campaigns_data.append({
                            'ID': c['id'],
                            'Chain': {
                                1: "ETH",
                                10: "OP",
                                137: "POLY",
                                8453: "BASE",
                                42161: "ARB"
                            }.get(c['platform_chain_id'], str(c['platform_chain_id'])),
                            'Gauge': c['campaign']['gauge'][:10] + '...',
                            'Manager': c['campaign']['manager'][:10] + '...',
                            'Periods': len(c.get('periods', [])),
                            'Status': 'Closed' if c['is_closed'] else c.get('status_info', {}).get('readable', 'Active'),
                            'Full Gauge': c['campaign']['gauge']
                        })
                    
                    campaigns_df = pd.DataFrame(campaigns_data)
                    
                    # Display with filters
                    col1, col2 = st.columns(2)
                    with col1:
                        status_filter = st.selectbox(
                            "Filter by Status",
                            ["All", "Active", "Closed"],
                            key="status_filter"
                        )
                    
                    with col2:
                        search_gauge = st.text_input(
                            "Search by Gauge Address",
                            placeholder="0x...",
                            key="gauge_search"
                        )
                    
                    # Apply filters
                    if status_filter != "All":
                        if status_filter == "Active":
                            campaigns_df = campaigns_df[~campaigns_df['Status'].str.contains('Closed')]
                        else:
                            campaigns_df = campaigns_df[campaigns_df['Status'].str.contains('Closed')]
                    
                    if search_gauge:
                        campaigns_df = campaigns_df[
                            campaigns_df['Full Gauge'].str.lower().str.contains(search_gauge.lower())
                        ]
                    
                    # Display table
                    st.dataframe(
                        campaigns_df[['ID', 'Chain', 'Gauge', 'Manager', 'Periods', 'Status']],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No campaigns found.")
                    
            except Exception as e:
                st.error(f"Error loading campaigns: {str(e)}")
    
    # Footer with instructions
    st.markdown("---")
    with st.expander("ℹ️ How to Use"):
        st.markdown("""
        **Check Your Eligibility:**
        1. Enter your wallet address
        2. Select a protocol (Curve, Balancer, etc.)
        3. Optionally filter by chain
        4. Click "Check My Eligibility"
        
        **Generate Proofs:**
        - For periods showing "No Proof", click "Generate Proof"
        - This will create the proof data needed to claim rewards
        
        **View All Campaigns:**
        - Click "View All Campaigns" to see all campaigns
        - Filter by status or search by gauge address
        
        **Claim Rewards:**
        - Use the generated proofs to claim rewards on-chain
        - Or download pre-generated proofs from the VoteMarket API
        """)
    
    # Links
    st.markdown("""
    <div style='text-align: center; padding: 20px; color: #666;'>
        <a href='https://github.com/stake-dao/api/tree/main/api/votemarket' target='_blank'>VoteMarket API</a> | 
        <a href='https://votemarket.stakedao.org' target='_blank'>VoteMarket App</a> | 
        <a href='https://github.com/stake-dao/votemarket-proof-toolkit' target='_blank'>GitHub</a>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()