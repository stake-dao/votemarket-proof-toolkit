"""
Proof Generator Page
Generate cryptographic proofs for voting participation
"""

import streamlit as st
import json
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path to import toolkit
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from votemarket_toolkit.proofs import VoteMarketProofs

st.set_page_config(page_title="Proof Generator", page_icon="🔐", layout="wide")

st.title("🔐 Proof Generator")
st.markdown("Generate cryptographic proofs for voting participation and rewards")

# Tabs for different proof types
tab1, tab2, tab3 = st.tabs(["👤 User Proof", "⚖️ Gauge Proof", "🧱 Block Info"])

# ========== USER PROOF TAB ==========
with tab1:
    st.markdown("### Generate User Voting Proof")
    st.markdown("Generate proof of a user's vote participation at a specific block")

    col1, col2 = st.columns(2)

    with col1:
        user_protocol = st.selectbox(
            "Protocol",
            options=["curve", "balancer", "frax", "fxn", "pendle"],
            index=0,
            key="user_protocol"
        )

        user_gauge = st.text_input(
            "Gauge Address",
            placeholder="0x...",
            help="Address of the gauge to check",
            key="user_gauge"
        )

    with col2:
        user_chain_options = {
            "Ethereum": 1,
            "Optimism": 10,
            "Polygon": 137,
            "Base": 8453,
            "Arbitrum": 42161
        }

        user_chain_name = st.selectbox(
            "Chain",
            options=list(user_chain_options.keys()),
            index=0,  # Default to Ethereum
            key="user_chain"
        )
        user_chain_id = user_chain_options[user_chain_name]

        user_address = st.text_input(
            "User Address",
            placeholder="0x...",
            help="Address of the user who voted",
            key="user_address"
        )

    user_block = st.number_input(
        "Block Number",
        min_value=1,
        value=20000000,
        step=1,
        help="Block number at which to generate the proof",
        key="user_block"
    )

    if st.button("🔐 Generate User Proof", type="primary", key="gen_user_proof"):
        # Validation
        if not user_gauge or not user_gauge.startswith("0x"):
            st.error("Please enter a valid gauge address")
        elif not user_address or not user_address.startswith("0x"):
            st.error("Please enter a valid user address")
        else:
            with st.spinner("Generating user proof..."):
                try:
                    proof_manager = VoteMarketProofs(chain_id=user_chain_id)

                    proof = proof_manager.get_user_proof(
                        protocol=user_protocol,
                        gauge_address=user_gauge,
                        user_address=user_address,
                        block_number=user_block
                    )

                    st.success("✅ User proof generated successfully!")

                    # Display proof details
                    st.markdown("#### Proof Details")

                    detail_col1, detail_col2 = st.columns(2)

                    with detail_col1:
                        st.write(f"**Block Number:** {user_block}")
                        st.write(f"**Protocol:** {user_protocol}")
                        st.write(f"**Chain:** {user_chain_name}")

                    with detail_col2:
                        st.write(f"**Gauge:** `{user_gauge[:10]}...{user_gauge[-8:]}`")
                        st.write(f"**User:** `{user_address[:10]}...{user_address[-8:]}`")

                    # Show proof data
                    st.markdown("#### Generated Proof")

                    with st.expander("📋 View Full Proof Data"):
                        st.json(proof)

                    # Export
                    proof_json = json.dumps(proof, indent=2)

                    st.download_button(
                        label="📥 Download Proof (JSON)",
                        data=proof_json,
                        file_name=f"user_proof_{user_address[:8]}_{user_block}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )

                except Exception as e:
                    st.error(f"Error generating proof: {str(e)}")
                    import traceback
                    with st.expander("View Error Details"):
                        st.code(traceback.format_exc())

    # Info
    st.markdown("---")
    st.info("""
    **User Proof** is used to verify a user's vote slope data at a specific block.
    This proof is required for users to claim their voting rewards.

    **Use case:** Submit this proof to the oracle before a user attempts to claim rewards.
    """)

# ========== GAUGE PROOF TAB ==========
with tab2:
    st.markdown("### Generate Gauge Voting Weight Proof")
    st.markdown("Generate proof of gauge voting weight at a specific epoch")

    col1, col2 = st.columns(2)

    with col1:
        gauge_protocol = st.selectbox(
            "Protocol",
            options=["curve", "balancer", "frax", "fxn", "pendle"],
            index=0,
            key="gauge_protocol"
        )

        gauge_address = st.text_input(
            "Gauge Address",
            placeholder="0x...",
            help="Address of the gauge",
            key="gauge_address"
        )

    with col2:
        gauge_chain_options = {
            "Ethereum": 1,
            "Optimism": 10,
            "Polygon": 137,
            "Base": 8453,
            "Arbitrum": 42161
        }

        gauge_chain_name = st.selectbox(
            "Chain",
            options=list(gauge_chain_options.keys()),
            index=0,  # Default to Ethereum
            key="gauge_chain"
        )
        gauge_chain_id = gauge_chain_options[gauge_chain_name]

        gauge_block = st.number_input(
            "Block Number",
            min_value=1,
            value=20000000,
            step=1,
            help="Block number for the proof",
            key="gauge_block"
        )

    gauge_epoch = st.number_input(
        "Current Epoch (Unix Timestamp)",
        min_value=1,
        value=1700000000,
        step=604800,  # 1 week
        help="Unix timestamp of the epoch",
        key="gauge_epoch"
    )

    if st.button("🔐 Generate Gauge Proof", type="primary", key="gen_gauge_proof"):
        # Validation
        if not gauge_address or not gauge_address.startswith("0x"):
            st.error("Please enter a valid gauge address")
        else:
            with st.spinner("Generating gauge proof..."):
                try:
                    proof_manager = VoteMarketProofs(chain_id=gauge_chain_id)

                    proof = proof_manager.get_gauge_proof(
                        protocol=gauge_protocol,
                        gauge_address=gauge_address,
                        current_epoch=gauge_epoch,
                        block_number=gauge_block
                    )

                    st.success("✅ Gauge proof generated successfully!")

                    # Display proof details
                    st.markdown("#### Proof Details")

                    detail_col1, detail_col2 = st.columns(2)

                    with detail_col1:
                        st.write(f"**Block Number:** {gauge_block}")
                        st.write(f"**Epoch:** {gauge_epoch}")
                        st.write(f"**Epoch Date:** {datetime.fromtimestamp(gauge_epoch).strftime('%Y-%m-%d %H:%M:%S')}")

                    with detail_col2:
                        st.write(f"**Protocol:** {gauge_protocol}")
                        st.write(f"**Chain:** {gauge_chain_name}")
                        st.write(f"**Gauge:** `{gauge_address[:10]}...{gauge_address[-8:]}`")

                    # Show proof data
                    st.markdown("#### Generated Proof")

                    with st.expander("📋 View Full Proof Data"):
                        st.json(proof)

                    # Export
                    proof_json = json.dumps(proof, indent=2)

                    st.download_button(
                        label="📥 Download Proof (JSON)",
                        data=proof_json,
                        file_name=f"gauge_proof_{gauge_address[:8]}_{gauge_epoch}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )

                except Exception as e:
                    st.error(f"Error generating proof: {str(e)}")
                    import traceback
                    with st.expander("View Error Details"):
                        st.code(traceback.format_exc())

    # Info
    st.markdown("---")
    st.info("""
    **Gauge Proof** verifies the voting weight (point data) of a gauge at a specific epoch.
    This proof is required for the campaign to distribute rewards based on voting power.

    **Use case:** Submit this proof to the oracle to update gauge point data for reward calculations.
    """)

# ========== BLOCK INFO TAB ==========
with tab3:
    st.markdown("### Get Block Information")
    st.markdown("Retrieve block hash, header, and timestamp for a specific block")

    col1, col2 = st.columns(2)

    with col1:
        block_chain_options = {
            "Ethereum": 1,
            "Optimism": 10,
            "Polygon": 137,
            "Base": 8453,
            "Arbitrum": 42161
        }

        block_chain_name = st.selectbox(
            "Chain",
            options=list(block_chain_options.keys()),
            index=0,  # Default to Ethereum
            key="block_chain"
        )
        block_chain_id = block_chain_options[block_chain_name]

    with col2:
        block_number = st.number_input(
            "Block Number",
            min_value=1,
            value=20000000,
            step=1,
            help="Block number to query",
            key="block_number"
        )

    if st.button("🧱 Get Block Info", type="primary", key="get_block_info"):
        with st.spinner("Fetching block information..."):
            try:
                proof_manager = VoteMarketProofs(chain_id=block_chain_id)

                block_info = proof_manager.get_block_info(block_number=block_number)

                st.success("✅ Block information retrieved successfully!")

                # Display block info
                st.markdown("#### Block Information")

                info_col1, info_col2 = st.columns(2)

                with info_col1:
                    st.write(f"**Block Number:** {block_number}")
                    st.write(f"**Chain:** {block_chain_name}")

                    if 'timestamp' in block_info:
                        timestamp = block_info['timestamp']
                        st.write(f"**Timestamp:** {timestamp}")
                        st.write(f"**Date:** {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')}")

                with info_col2:
                    if 'block_hash' in block_info:
                        st.write(f"**Block Hash:**")
                        st.code(block_info['block_hash'], language=None)

                # Show full data
                st.markdown("#### Full Block Data")

                with st.expander("📋 View Complete Block Info"):
                    st.json(block_info)

                # Export
                block_json = json.dumps(block_info, indent=2)

                st.download_button(
                    label="📥 Download Block Info (JSON)",
                    data=block_json,
                    file_name=f"block_info_{block_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )

            except Exception as e:
                st.error(f"Error fetching block info: {str(e)}")
                import traceback
                with st.expander("View Error Details"):
                    st.code(traceback.format_exc())

    # Info
    st.markdown("---")
    st.info("""
    **Block Info** provides the block hash, RLP-encoded header, and timestamp for a specific block.
    This information is needed for submitting block headers to the oracle.

    **Use case:** Verify block data before submitting proofs or check historical block information.
    """)

# General info section
st.markdown("---")
st.markdown("### ℹ️ About Cryptographic Proofs")

st.markdown("""
The VoteMarket system uses cryptographic proofs to verify on-chain voting data without requiring
the oracle to maintain full blockchain state.

**Three Types of Proofs:**

1. **User Proof**: Proves that a user voted for a specific gauge at a specific block
   - Contains account proof and storage proof for the user's vote slope
   - Required for users to claim their voting rewards

2. **Gauge Proof**: Proves the voting weight of a gauge at an epoch
   - Contains gauge controller proof and point data proof
   - Required for calculating reward distribution

3. **Block Info**: Provides verified block header data
   - Used to anchor proofs to specific blockchain states
   - Must be submitted to oracle before other proofs

**Workflow:**
1. Generate block info for the target block
2. Generate gauge proof for reward calculations
3. Generate user proof for each user who wants to claim
4. Submit all proofs to the oracle contract
5. Users can now claim their rewards
""")
