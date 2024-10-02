"""Example of how to query active campaigns for a platform."""

import os
from typing import List
from dotenv import load_dotenv
from shared.constants import GlobalConstants
from shared.types import Campaign
from votes.main import VMVotes
from eth_utils import to_checksum_address

load_dotenv()

CHAIN_ID = 42161  # Arbitrum
PLATFORM_ADDRESS = to_checksum_address(
    "0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e".lower()
)


vm_votes = VMVotes(CHAIN_ID)


def main():
    """Using a contract creation to retrieve complex data easily."""
    # Query active campaigns (on a chain id / platform address)
    active_campaigns: List[Campaign] = vm_votes.get_active_campaigns(
        CHAIN_ID, PLATFORM_ADDRESS
    )

    print(f"Number of active campaigns: {len(active_campaigns)}")

    for campaign in active_campaigns:
        print("\nCampaign Details:")
        print(f"ID: {campaign['id']}")
        print(f"Chain ID: {campaign['chain_id']}")
        print(f"Platform Address: {campaign['platform_address']}")
        print(f"Gauge: {campaign['gauge']}")
        print(f"Manager: {campaign['manager']}")
        print(f"Reward Token: {campaign['reward_token']}")
        print(f"Number of Periods: {campaign['number_of_periods']}")
        print(f"Max Reward Per Vote: {campaign['max_reward_per_vote']}")
        print(f"Total Reward Amount: {campaign['total_reward_amount']}")
        print(f"Total Distributed: {campaign['total_distributed']}")
        print(f"Start Timestamp: {campaign['start_timestamp']}")
        print(f"End Timestamp: {campaign['end_timestamp']}")
        print(f"Hook: {campaign['hook']}")


if __name__ == "__main__":
    main()
