import sys
import time
from pathlib import Path

# Add the script directory to Python path
script_dir = str(Path(__file__).parent.parent.parent / "script")
sys.path.insert(0, script_dir)

from eth_utils import to_checksum_address
from votemarket_toolkit.utils import get_rounded_epoch, load_json
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://arb1.arbitrum.io/rpc"))

MANAGER_ADDRESS = "0x8898502BA35AB64b3562aBC509Befb7Eb178D4df"
VOTEMARKET_ADDRESS = "0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5"
VOTEMARKET_ABI = load_json("src/votemarket_toolkit/resources/abi/vm_platform.json")


def close_campaign_l2(campaign_id: int) -> dict:
    """
    Closes a campaign directly on L2 (Arbitrum).

    Args:
        campaign_id: ID of the campaign to close
    """
    # Initialize contract
    contract = w3.eth.contract(
        address=to_checksum_address(VOTEMARKET_ADDRESS),
        abi=VOTEMARKET_ABI,
    )

    # Build transaction
    tx = contract.functions.closeCampaign(campaign_id).build_transaction(
        {
            "from": to_checksum_address(MANAGER_ADDRESS),
            "gas": 400_000,
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(MANAGER_ADDRESS),
        }
    )
    return tx


def get_campaign_timing_info(campaign_id: int) -> dict:
    """
    Helper function to check campaign timing and closing eligibility.

    Returns:
        Dict containing timing information and closing status
    """
    # Initialize contract
    votemarket_contract = w3.eth.contract(
        address=to_checksum_address(VOTEMARKET_ADDRESS),
        abi=VOTEMARKET_ABI,
    )

    # Get campaign infos
    campaign_infos = votemarket_contract.functions.campaignById(
        campaign_id
    ).call()

    start_timestamp = campaign_infos[8]
    end_timestamp = campaign_infos[9]

    current_epoch = get_rounded_epoch(int(time.time()))

    # Calculate windows
    CLAIM_WINDOW = 24 * 7 * 24 * 3600  # 24 weeks in seconds
    CLOSE_WINDOW = 4 * 7 * 24 * 3600  # 4 weeks in seconds

    claim_window_end = end_timestamp + CLAIM_WINDOW
    close_window_end = end_timestamp + CLOSE_WINDOW

    return {
        "current_epoch": current_epoch,
        "start_epoch": start_timestamp,
        "end_epoch": end_timestamp,
        "claim_window_end": claim_window_end,
        "close_window_end": close_window_end,
        "status": (
            "not_started"
            if current_epoch < start_timestamp
            else (
                "active"
                if current_epoch < end_timestamp
                else (
                    "in_claim_window"
                    if current_epoch < claim_window_end
                    else (
                        "in_close_window"
                        if current_epoch < close_window_end
                        else "after_close_window"
                    )
                )
            )
        ),
    }
