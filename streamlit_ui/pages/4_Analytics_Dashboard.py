"""
Analytics Dashboard Page
View historical analytics and market data
"""

import streamlit as st
import asyncio
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path to import toolkit
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from votemarket_toolkit.analytics import AnalyticsService

st.set_page_config(page_title="Analytics Dashboard", page_icon="📈", layout="wide")

st.title("📈 Analytics Dashboard")
st.markdown("View historical analytics and market intelligence")

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

# Tabs for different analytics views
tab1, tab2, tab3 = st.tabs(["📊 Market Snapshot", "📜 Round History", "⚖️ Gauge History"])

# ========== MARKET SNAPSHOT TAB ==========
with tab1:
    st.markdown("### Current Market Snapshot")
    st.markdown("Live $/vote metrics across all active campaigns")

    if st.button("🔄 Load Market Snapshot", type="primary", key="load_snapshot"):
        with st.spinner(f"Loading market snapshot for {protocol} on {chain_name}..."):
            try:
                service = AnalyticsService()

                snapshot = asyncio.run(service.get_current_market_snapshot(
                    protocol=protocol,
                    chain_id=chain_id
                ))

                if snapshot:
                    st.success(f"✅ Loaded market snapshot with {len(snapshot)} campaigns")

                    # Summary metrics
                    st.markdown("#### Market Overview")

                    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

                    # Calculate aggregates
                    total_campaigns = len(snapshot)
                    avg_dollar_per_vote = sum(s.get('dollarPerVote', 0) for s in snapshot) / total_campaigns if total_campaigns > 0 else 0
                    max_dollar_per_vote = max((s.get('dollarPerVote', 0) for s in snapshot), default=0)
                    total_value = sum(s.get('totalValue', 0) for s in snapshot)

                    with metric_col1:
                        st.metric("Active Campaigns", total_campaigns)

                    with metric_col2:
                        st.metric("Avg $/Vote", f"${avg_dollar_per_vote:.4f}")

                    with metric_col3:
                        st.metric("Max $/Vote", f"${max_dollar_per_vote:.4f}")

                    with metric_col4:
                        st.metric("Total Market Value", f"${total_value:,.2f}")

                    st.markdown("---")

                    # Campaign table
                    st.markdown("#### Campaign Details")

                    # Create DataFrame
                    df_data = []
                    for campaign in snapshot:
                        df_data.append({
                            'Campaign ID': campaign.get('campaignId', 'N/A'),
                            'Gauge': campaign.get('gauge', 'N/A')[:20] + '...' if len(campaign.get('gauge', '')) > 20 else campaign.get('gauge', 'N/A'),
                            'Token': campaign.get('rewardToken', {}).get('symbol', 'N/A'),
                            'Total Value': f"${campaign.get('totalValue', 0):,.2f}",
                            '$/Vote': f"${campaign.get('dollarPerVote', 0):.4f}",
                            'Remaining Periods': campaign.get('remainingPeriods', 0),
                        })

                    df = pd.DataFrame(df_data)

                    # Sort by $/Vote descending
                    df_sorted = df.sort_values('$/Vote', ascending=False)

                    st.dataframe(df_sorted, use_container_width=True, hide_index=True)

                    # Export
                    st.markdown("---")
                    import json
                    json_data = json.dumps(snapshot, indent=2)

                    st.download_button(
                        label="📥 Download Market Snapshot (JSON)",
                        data=json_data,
                        file_name=f"market_snapshot_{protocol}_{chain_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )

                else:
                    st.warning("No market data available for this protocol/chain combination")

            except Exception as e:
                st.error(f"Error loading market snapshot: {str(e)}")
                import traceback
                with st.expander("View Error Details"):
                    st.code(traceback.format_exc())

    st.markdown("---")
    st.info("""
    **Market Snapshot** shows real-time efficiency metrics for all active campaigns.
    The $/vote metric indicates how much value each vote receives in rewards.

    Higher $/vote = more attractive for voters
    """)

# ========== ROUND HISTORY TAB ==========
with tab2:
    st.markdown("### Historical Round Data")
    st.markdown("View metadata and analytics from past voting rounds")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📜 Load Round Metadata", key="load_rounds"):
            with st.spinner(f"Loading round metadata for {protocol}..."):
                try:
                    service = AnalyticsService()

                    rounds = asyncio.run(service.fetch_rounds_metadata(protocol=protocol))

                    if rounds:
                        st.session_state.rounds_metadata = rounds
                        st.success(f"✅ Loaded {len(rounds)} rounds")

                        # Create DataFrame
                        df_data = []
                        for round_info in rounds:
                            df_data.append({
                                'Round ID': round_info.get('round', 'N/A'),
                                'Start Block': round_info.get('startBlock', 'N/A'),
                                'End Block': round_info.get('endBlock', 'N/A'),
                                'Status': round_info.get('status', 'N/A'),
                            })

                        df = pd.DataFrame(df_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)

                    else:
                        st.warning("No round metadata available")

                except Exception as e:
                    st.error(f"Error loading rounds: {str(e)}")

    with col2:
        if 'rounds_metadata' in st.session_state and st.session_state.rounds_metadata:
            round_ids = [r.get('round') for r in st.session_state.rounds_metadata]

            selected_round = st.selectbox(
                "Select Round to View",
                options=round_ids,
                key="selected_round"
            )

            if st.button("📊 Load Round Data", key="load_round_data"):
                with st.spinner(f"Loading data for round {selected_round}..."):
                    try:
                        service = AnalyticsService()

                        round_data = asyncio.run(service.fetch_round_data(
                            protocol=protocol,
                            round_id=selected_round
                        ))

                        if round_data:
                            st.success(f"✅ Loaded round {selected_round} data")

                            with st.expander(f"📋 Round {selected_round} Details"):
                                st.json(round_data)

                            # Export
                            import json
                            json_data = json.dumps(round_data, indent=2)

                            st.download_button(
                                label=f"📥 Download Round {selected_round} Data",
                                data=json_data,
                                file_name=f"round_{selected_round}_{protocol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json"
                            )

                        else:
                            st.warning(f"No data available for round {selected_round}")

                    except Exception as e:
                        st.error(f"Error loading round data: {str(e)}")

    st.markdown("---")
    st.info("""
    **Round History** provides historical analytics from the VoteMarket analytics repository.
    Each round represents a voting period with complete campaign and voting data.
    """)

# ========== GAUGE HISTORY TAB ==========
with tab3:
    st.markdown("### Gauge Historical Data")
    st.markdown("View historical analytics for a specific gauge")

    gauge_address = st.text_input(
        "Gauge Address",
        placeholder="0x...",
        help="Address of the gauge to analyze",
        key="gauge_address"
    )

    if st.button("📈 Load Gauge History", type="primary", key="load_gauge"):
        if not gauge_address or not gauge_address.startswith("0x"):
            st.error("Please enter a valid gauge address")
        else:
            with st.spinner(f"Loading history for gauge {gauge_address[:10]}..."):
                try:
                    service = AnalyticsService()

                    history = asyncio.run(service.fetch_gauge_history(
                        protocol=protocol,
                        gauge_address=gauge_address
                    ))

                    if history:
                        st.success(f"✅ Loaded historical data for gauge")

                        # Display summary
                        st.markdown("#### Historical Analytics")

                        with st.expander("📋 View Full Gauge History"):
                            st.json(history)

                        # Export
                        import json
                        json_data = json.dumps(history, indent=2)

                        st.download_button(
                            label="📥 Download Gauge History",
                            data=json_data,
                            file_name=f"gauge_history_{gauge_address[:8]}_{protocol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )

                    else:
                        st.warning("No historical data available for this gauge")

                except Exception as e:
                    st.error(f"Error loading gauge history: {str(e)}")
                    import traceback
                    with st.expander("View Error Details"):
                        st.code(traceback.format_exc())

    st.markdown("---")
    st.info("""
    **Gauge History** shows historical campaign and voting data for a specific gauge.
    Use this to analyze trends and past performance.
    """)

# General info section
st.markdown("---")
st.markdown("### ℹ️ About Analytics Data")

st.markdown("""
The analytics data is sourced from the [VoteMarket Analytics Repository](https://github.com/stake-dao/votemarket-analytics).

**Data Includes:**
- Historical round metadata and campaign details
- $/vote efficiency metrics over time
- Gauge-specific voting and reward history
- Market snapshots showing current opportunities

**Use Cases:**
- Compare campaign efficiency across protocols
- Track historical voting trends
- Identify best opportunities for voters
- Analyze gauge performance over time
""")
