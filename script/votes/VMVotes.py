from typing import List, Dict, Any
from shared.constants import GaugeControllerConstants
from votes.query_votes import query_gauge_votes
from votes.query_campaigns import query_active_campaigns
from shared.web3_service import Web3Service
from shared.exceptions import VoteMarketVotesException
from w3multicall.multicall import W3Multicall


class VMVotes:
    def __init__(self, rpc_url: str):
        self.web3_service = Web3Service(rpc_url)

    async def get_gauge_votes(
        self, protocol: str, gauge_address: str, block_number: int
    ) -> List[Dict[str, Any]]:
        try:
            return await query_gauge_votes(
                self.web3_service.w3, protocol, gauge_address, block_number
            )
        except Exception as e:
            raise VoteMarketVotesException(f"Error querying gauge votes: {str(e)}")

    async def get_eligible_users(
        self, protocol: str, gauge_address: str, current_period: int, block_number: int
    ) -> List[Dict[str, Any]]:
        try:
            w3 = self.web3_service.w3
            multicall = W3Multicall(w3)

            gauge_controller_address = w3.to_checksum_address(
                GaugeControllerConstants.GAUGE_CONTROLLER[protocol]
            )

            votes = await self.get_gauge_votes(protocol, gauge_address, block_number)
            unique_users = list(set(vote["user"] for vote in votes))

            for user in unique_users:
                multicall.add(
                    W3Multicall.Call(
                        gauge_controller_address,
                        "last_user_vote(address,address)(uint256)",
                        [
                            w3.to_checksum_address(user),
                            w3.to_checksum_address(gauge_address),
                        ],
                    )
                )
                multicall.add(
                    W3Multicall.Call(
                        gauge_controller_address,
                        "vote_user_slopes(address,address)(int128,int128,uint256)",
                        [
                            w3.to_checksum_address(user),
                            w3.to_checksum_address(gauge_address),
                        ],
                    )
                )

            results = multicall.call(block_number)

            eligible_users = []

            for i in range(0, len(results), 2):
                user = unique_users[i // 2]
                last_vote = results[i]
                slope, power, end = results[i + 1]

                if current_period < end and current_period > last_vote:
                    eligible_users.append(
                        {
                            "user": user,
                            "last_vote": last_vote,
                            "slope": slope,
                            "power": power,
                            "end": end,
                        }
                    )

            return eligible_users
        except Exception as e:
            raise VoteMarketVotesException(f"Error getting eligible users: {str(e)}")

    def get_active_campaigns(self, chain_id: int, platform: str) -> List[Dict[str, Any]]:
        try:
            return query_active_campaigns(chain_id, platform)
        except Exception as e:
            raise VoteMarketVotesException(f"Error querying active campaigns: {str(e)}")
