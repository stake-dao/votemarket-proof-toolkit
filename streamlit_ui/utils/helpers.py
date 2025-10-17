"""
Helper utilities for the Streamlit UI
"""

from typing import Dict, List, Any
from datetime import datetime
import streamlit as st


def format_address(address: str, prefix_len: int = 10, suffix_len: int = 8) -> str:
    """
    Format an Ethereum address for display

    Args:
        address: Full Ethereum address
        prefix_len: Number of characters to show at start
        suffix_len: Number of characters to show at end

    Returns:
        Formatted address string
    """
    if not address or len(address) < prefix_len + suffix_len:
        return address

    return f"{address[:prefix_len]}...{address[-suffix_len:]}"


def format_token_amount(amount: int, decimals: int = 18, precision: int = 4) -> str:
    """
    Format a token amount from wei to human-readable

    Args:
        amount: Token amount in smallest unit (wei)
        decimals: Token decimal places
        precision: Number of decimal places to display

    Returns:
        Formatted token amount
    """
    return f"{amount / 10**decimals:,.{precision}f}"


def format_usd_value(value: float, precision: int = 2) -> str:
    """
    Format a USD value

    Args:
        value: Dollar amount
        precision: Number of decimal places

    Returns:
        Formatted USD string
    """
    return f"${value:,.{precision}f}"


def get_status_emoji(status: str) -> str:
    """
    Get emoji for campaign status

    Args:
        status: Campaign status string

    Returns:
        Status emoji
    """
    status_map = {
        'ACTIVE': '🟢',
        'CLOSED': '🔴',
        'CLOSABLE_BY_MANAGER': '🟡',
        'CLOSABLE_BY_ANYONE': '🟠',
        'PENDING': '⚪',
        'UNKNOWN': '⚫'
    }
    return status_map.get(status, '⚪')


def get_boolean_emoji(value: bool) -> str:
    """
    Get emoji for boolean value

    Args:
        value: Boolean value

    Returns:
        Checkmark or X emoji
    """
    return '✅' if value else '❌'


def validate_ethereum_address(address: str) -> bool:
    """
    Validate Ethereum address format

    Args:
        address: Address to validate

    Returns:
        True if valid, False otherwise
    """
    if not address:
        return False

    if not address.startswith('0x'):
        return False

    if len(address) != 42:
        return False

    try:
        int(address, 16)
        return True
    except ValueError:
        return False


def create_download_filename(
    prefix: str,
    identifier: str = None,
    extension: str = "json"
) -> str:
    """
    Create a timestamped filename for downloads

    Args:
        prefix: File prefix
        identifier: Optional identifier to include
        extension: File extension (without dot)

    Returns:
        Formatted filename
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if identifier:
        return f"{prefix}_{identifier}_{timestamp}.{extension}"
    else:
        return f"{prefix}_{timestamp}.{extension}"


def cache_data_with_ttl(ttl: int = 300):
    """
    Decorator for caching data with TTL

    Args:
        ttl: Time to live in seconds

    Returns:
        Streamlit cache decorator
    """
    return st.cache_data(ttl=ttl)


def show_error_with_traceback(error: Exception, show_details: bool = True):
    """
    Display an error with optional traceback

    Args:
        error: The exception to display
        show_details: Whether to show traceback in expander
    """
    st.error(f"Error: {str(error)}")

    if show_details:
        import traceback
        with st.expander("View Error Details"):
            st.code(traceback.format_exc())


def create_metric_cards(metrics: List[Dict[str, Any]], columns: int = 4):
    """
    Create a row of metric cards

    Args:
        metrics: List of metric dicts with 'label', 'value', and optional 'delta', 'help'
        columns: Number of columns to use
    """
    cols = st.columns(columns)

    for idx, metric in enumerate(metrics):
        col_idx = idx % columns
        with cols[col_idx]:
            st.metric(
                label=metric.get('label', ''),
                value=metric.get('value', ''),
                delta=metric.get('delta'),
                help=metric.get('help')
            )


def format_timestamp(timestamp: int, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    Format Unix timestamp to readable string

    Args:
        timestamp: Unix timestamp
        format_str: strftime format string

    Returns:
        Formatted timestamp string
    """
    return datetime.fromtimestamp(timestamp).strftime(format_str)


def create_info_section(title: str, content: str, icon: str = "ℹ️"):
    """
    Create a styled info section

    Args:
        title: Section title
        content: Section content (markdown supported)
        icon: Emoji icon
    """
    st.markdown(f"### {icon} {title}")
    st.markdown(content)


def flatten_campaign_for_export(campaign: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten campaign data structure for CSV export

    Args:
        campaign: Campaign data dictionary

    Returns:
        Flattened dictionary
    """
    campaign_info = campaign.get('campaign', {})
    token_info = campaign.get('reward_token', {})
    status_info = campaign.get('status_info', {})

    return {
        'ID': campaign.get('id'),
        'Gauge': campaign_info.get('gauge', ''),
        'Manager': campaign_info.get('manager', ''),
        'Reward Token Address': campaign_info.get('reward_token', ''),
        'Token Symbol': token_info.get('symbol', ''),
        'Token Name': token_info.get('name', ''),
        'Token Decimals': token_info.get('decimals', 18),
        'Token Price': token_info.get('price', 0),
        'Total Reward Amount': campaign_info.get('total_reward_amount', 0),
        'Max Reward Per Vote': campaign_info.get('max_reward_per_vote', 0),
        'End Timestamp': campaign_info.get('end_timestamp', 0),
        'Number of Periods': campaign_info.get('number_of_periods', 0),
        'Remaining Periods': campaign.get('remaining_periods', 0),
        'Is Closed': campaign.get('is_closed', False),
        'Is Whitelist Only': campaign.get('is_whitelist_only', False),
        'Status': status_info.get('status', ''),
        'Can Close': status_info.get('can_close', False),
        'Who Can Close': status_info.get('who_can_close', ''),
    }


def create_styled_header(title: str, subtitle: str = None):
    """
    Create a styled page header

    Args:
        title: Main title
        subtitle: Optional subtitle
    """
    st.markdown(f'<div class="main-header">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="sub-header">{subtitle}</div>', unsafe_allow_html=True)
