"""
VoteMarket Toolkit - Streamlit UI
Main application entry point
"""

import streamlit as st

# Page configuration
st.set_page_config(
    page_title="VoteMarket Toolkit",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .stButton>button {
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

# Main page
st.markdown('<div class="main-header">🗳️ VoteMarket Toolkit</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Manage campaigns, check claims, and generate proofs</div>', unsafe_allow_html=True)

# Welcome content
st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📊 Active Campaigns")
    st.write("Browse and analyze active voting campaigns across multiple chains and protocols.")
    st.page_link("pages/1_Active_Campaigns.py", label="View Campaigns →", icon="📊")

with col2:
    st.markdown("### 🔍 User Claims")
    st.write("Check user claim eligibility and proof status for specific campaigns.")
    st.page_link("pages/2_User_Claims.py", label="Check Claims →", icon="🔍")

with col3:
    st.markdown("### 🔐 Proof Generator")
    st.write("Generate cryptographic proofs for voting participation and rewards.")
    st.page_link("pages/3_Proof_Generator.py", label="Generate Proofs →", icon="🔐")

st.markdown("---")

# Quick stats section
st.markdown("### 📈 Quick Stats")

info_col1, info_col2, info_col3, info_col4 = st.columns(4)

with info_col1:
    st.metric(
        label="Supported Protocols",
        value="5",
        help="Curve, Balancer, Frax, FXN, Pendle"
    )

with info_col2:
    st.metric(
        label="Supported Chains",
        value="5",
        help="Ethereum, Arbitrum, Optimism, Base, Polygon"
    )

with info_col3:
    st.metric(
        label="Toolkit Version",
        value="1.0.6"
    )

with info_col4:
    st.metric(
        label="API Status",
        value="✅ Active",
        delta="Operational"
    )

# Footer info
st.markdown("---")
st.markdown("""
    **Features:**
    - 🔄 Real-time campaign data from on-chain sources
    - 🔐 Cryptographic proof generation for claims
    - 📊 Multi-chain and multi-protocol support
    - 💰 Token price integration and USD value calculations
    - ⚡ Optimized batch processing for fast queries

    **Documentation:** [GitHub](https://github.com/stake-dao/votemarket-proof-toolkit)
""")
