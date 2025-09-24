from typing import Dict, List

from eth_utils import to_checksum_address
from w3multicall.multicall import W3Multicall

from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.exceptions import VoteMarketDataException
from votemarket_toolkit.shared.services.web3_service import Web3Service
from votemarket_toolkit.shared.types import EligibleUser
from votemarket_toolkit.utils.blockchain import get_rounded_epoch
from votemarket_toolkit.votes.services.votes_service import votes_service


class VoteMarketDataService:
    def __init__(self, chain_id: int):
        self.chain_id = chain_id
        self.web3_service = Web3Service.get_instance(chain_id)

    def get_web3_service_for_chain(self, chain_id: int) -> Web3Service:
        """Get Web3Service for a specific chain"""
        return Web3Service.get_instance(chain_id)

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
            w3 = self.web3_service.w3

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

            gauge_controller = registry.get_gauge_controller(protocol)
            if not gauge_controller:
                raise VoteMarketDataException(
                    f"No gauge controller found for protocol: {protocol}"
                )
            gauge_controller_address = to_checksum_address(gauge_controller)

            gauge_votes = await votes_service.get_gauge_votes(
                protocol, gauge_address, block_number
            )
            unique_users = list(set(vote.user for vote in gauge_votes.votes))

            for user in unique_users:
                if protocol == "pendle":
                    multicall.add(
                        W3Multicall.Call(
                            gauge_controller_address,
                            "getUserPoolVote(address,address)(uint256,uint256,uint256)",
                            [
                                to_checksum_address(user),
                                to_checksum_address(gauge_address),
                            ],
                        )
                    )
                    ve_address = registry.get_ve_address(protocol)
                    if ve_address:
                        multicall.add(
                            W3Multicall.Call(
                                to_checksum_address(ve_address),
                                "positionData(address)(uint128,uint128)",
                                [to_checksum_address(user)],
                            )
                        )
                else:
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

                if protocol == "pendle":
                    last_vote = 0
                    power, _, slope = results[i]
                    end = results[i + 1][1]
                else:
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

        w3 = self.web3_service.w3
        multicall = W3Multicall(w3)

        platform_contract = self.web3_service.get_contract(
            platform, "vm_platform"
        )

        lens = platform_contract.functions.ORACLE().call()

        lens_address = to_checksum_address(lens.lower())

        lens_contract = self.web3_service.get_contract(
            lens_address, "oracle_lens"
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
