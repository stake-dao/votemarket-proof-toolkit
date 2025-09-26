""" 
get_gauge_votes
"""

import asyncio
from votes.services.votes_service import VotesService


async def main(): 
    service = VotesService(cache_dir="cache")
    votes = await service.get_gauge_votes(
        protocol="curve", gauge_address="0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A", block_number=23447400
    )
    print(votes)


if __name__ == "__main__":
    asyncio.run(main())

# TODO : Example for that