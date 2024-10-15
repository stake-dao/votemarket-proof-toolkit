"""Example of how to query voters for a gauge."""

import asyncio
import os
from dotenv import load_dotenv
from eth_utils import to_checksum_address
from shared.constants import GlobalConstants
from votes.main import VoteMarketVotes

load_dotenv()

vm_votes = VoteMarketVotes(1)

# Example parameters
PROTOCOL = "curve"
GAUGE_ADDRESS = to_checksum_address(
    "0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A".lower()
)  # sdCRV gauge
BLOCK_NUMBER = 20864159  # Max block number to check


async def main():
    """Query eligible users for a gauge."""
    # Query gauge votes
    gauge_votes = await vm_votes.get_gauge_votes(PROTOCOL, GAUGE_ADDRESS, BLOCK_NUMBER)

    print("Gauge Votes:")
    print(len(gauge_votes))

    # Get eligible users
    CURRENT_EPOCH = 1723680000
    eligible_users = await vm_votes.get_eligible_users(
        PROTOCOL, GAUGE_ADDRESS, CURRENT_EPOCH, BLOCK_NUMBER
    )

    print(f"\n{len(eligible_users)} users eligible for gauge {GAUGE_ADDRESS}:")
    for user in eligible_users:
        print(
            f"User: {user['user']}, Last Vote: {user['last_vote']}, Slope: {user['slope']}, Power: {user['power']}, End: {user['end']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
