import os
import asyncio
import time
from votes.VMVotes import VMVotes
from dotenv import load_dotenv

load_dotenv()

vm_votes = VMVotes(
    "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
)

# Example parameters
protocol = "curve"
gauge_address = "0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A" # sdCRV gauge
block_number = 20530737 # Max block number to check

async def main():
    # Query gauge votes
    gauge_votes = await vm_votes.get_gauge_votes(protocol, gauge_address, block_number)

    print("Gauge Votes:")
    print(len(gauge_votes))


    # Get eligible users
    current_period = 1723680000
    eligible_users = await vm_votes.get_eligible_users(protocol, gauge_address, current_period, block_number)

    print("\nEligible Users:")
    print(len(eligible_users))
    for user in eligible_users:
        print(f"User: {user['user']}, Last Vote: {user['last_vote']}, Slope: {user['slope']}, Power: {user['power']}, End: {user['end']}")

if __name__ == "__main__":
    asyncio.run(main())
