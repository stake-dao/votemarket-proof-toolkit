"""Example of how to query active campaigns for a platform."""

import os
from typing import List
from dotenv import load_dotenv
from shared.types import Campaign
from votes.main import VoteMarketVotes
from eth_utils import to_checksum_address

load_dotenv()

CHAIN_ID = 42161  # Arbitrum
PLATFORM_ADDRESS = to_checksum_address(
    "0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e".lower()
)


vm_votes = VoteMarketVotes(CHAIN_ID)


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
        print(f"Platform Address: {PLATFORM_ADDRESS}")
        print(f"Gauge: {campaign['gauge']}")
        print(f"Listed Users: {campaign['listed_users']}")

if __name__ == "__main__":
    main()
