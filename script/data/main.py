from typing import Any, Dict, List

from data.query_campaigns import query_active_campaigns
from data.query_votes import query_gauge_votes
from eth_utils import to_checksum_address
from shared.constants import GaugeControllerConstants, GlobalConstants
from shared.exceptions import VoteMarketDataException
from shared.types import Campaign, EligibleUser
from shared.utils import get_rounded_epoch
from shared.web3_service import Web3Service
from w3multicall.multicall import W3Multicall


class VoteMarketData:
    def __init__(self, chain_id: int):
        rpc_url = GlobalConstants.get_rpc_url(chain_id)
        self.web3_service = Web3Service(chain_id, rpc_url)

    async def get_gauge_votes(
        self, protocol: str, gauge_address: str, block_number: int
    ) -> List[Dict[str, Any]]:
        try:
            return await query_gauge_votes(
                self.web3_service.w3, protocol, gauge_address, block_number
            )
        except Exception as e:
            raise VoteMarketDataException(
                f"Error querying gauge votes: {str(e)}"
            )

    async def get_eligible_users(
        self,
        protocol: str,
        gauge_address: str,
        current_epoch: int,
        block_number: int,
        chain_id: int = None,
        platform: str = None,
    ) -> List[EligibleUser]:
        # We always treat the epoch rounded to the day
        current_epoch = get_rounded_epoch(current_epoch)

        try:
            w3 = self.web3_service.get_w3()

            if chain_id is not None and platform is not None:
                epoch_blocks = self.get_epochs_block(
                    chain_id, platform, [current_epoch]
                )
                block_number = epoch_blocks[current_epoch]
                if block_number == 0:
                    raise VoteMarketDataException(
                        f"No block set for epoch {current_epoch}"
                    )

            multicall = W3Multicall(w3)

            gauge_controller_address = to_checksum_address(
                GaugeControllerConstants.GAUGE_CONTROLLER[protocol]
            )

            votes = await self.get_gauge_votes(
                protocol, gauge_address, block_number
            )
            unique_users = list(set(vote["user"] for vote in votes))

            for user in unique_users:
                multicall.add(
                    W3Multicall.Call(
                        gauge_controller_address,
                        "last_user_vote(address,address)(uint256)",
                        [
                            to_checksum_address(user),
                            to_checksum_address(gauge_address),
                        ],
                    )
                )
                multicall.add(
                    W3Multicall.Call(
                        gauge_controller_address,
                        "vote_user_slopes(address,address)(int128,int128,uint256)",
                        [
                            to_checksum_address(user),
                            to_checksum_address(gauge_address),
                        ],
                    )
                )

            results = multicall.call(block_number)

            eligible_users: List[EligibleUser] = []

            for i in range(0, len(results), 2):
                user = unique_users[i // 2]
                last_vote = results[i]
                slope, power, end = results[i + 1]

                if (
                    current_epoch < end
                    and current_epoch > last_vote
                    and slope > 0
                ):
                    eligible_users.append(
                        EligibleUser(
                            user=user,
                            last_vote=last_vote,
                            slope=slope,
                            power=power,
                            end=end,
                        )
                    )

            return eligible_users
        except Exception as e:
            raise VoteMarketDataException(
                f"Error getting eligible users: {str(e)}"
            )

    def get_epochs_block(
        self, chain_id: int, platform: str, epochs: List[int]
    ) -> Dict[int, int]:

        # We always treat the epoch rounded to the day
        epochs = [get_rounded_epoch(epoch) for epoch in epochs]

        if chain_id not in self.web3_service.w3:
            self.web3_service.add_chain(
                chain_id, GlobalConstants.get_rpc_url(chain_id)
            )

        w3 = self.web3_service.get_w3(chain_id)
        multicall = W3Multicall(w3)

        platform_contract = self.web3_service.get_contract(
            platform, "vm_platform", chain_id
        )
        lens = platform_contract.functions.ORACLE().call()
        lens_address = to_checksum_address(lens.lower())

        lens_contract = self.web3_service.get_contract(
            lens_address, "oracle_lens", chain_id
        )
        oracle_address = lens_contract.functions.oracle().call()
        oracle_address = to_checksum_address(oracle_address.lower())

        if oracle_address == "0x0000000000000000000000000000000000000000":
            return {epoch: 0 for epoch in epochs}

        for epoch in epochs:
            multicall.add(
                W3Multicall.Call(
                    oracle_address,
                    "epochBlockNumber(uint256)(bytes32,bytes32,uint256,uint256)",
                    [epoch],
                )
            )

        results = multicall.call()

        return {
            epochs[i]: results[i][2] if results[i][2] != 0 else 0
            for i in range(len(epochs))
        }

    def get_active_campaigns(
        self, chain_id: int, platform: str
    ) -> List[Campaign]:
        try:
            return query_active_campaigns(
                self.web3_service, chain_id, platform
            )
        except Exception as e:
            raise VoteMarketDataException(
                f"Error querying active campaigns: {str(e)}"
            )
