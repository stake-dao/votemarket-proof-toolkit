import json
from typing import Any, Dict, List, Optional, TypeVar

from eth_abi import decode, encode
from votemarket_proofs.shared.types import CampaignData
from web3 import Web3

T = TypeVar("T")


class ContractReader:
    """
    Contract reader that works with pre-compiled contract artifacts.
    Expects artifacts to be stored in a JSON format with bytecode.
    """

    # Cache for loaded contract artifacts
    _contract_artifacts: Dict[str, Dict] = {}

    @classmethod
    def load_artifact(cls, artifact_path: str) -> Dict:
        """
        Load a contract artifact from JSON file.
        """
        if artifact_path not in cls._contract_artifacts:
            with open(artifact_path, "r") as f:
                artifact = json.load(f)
                cls._contract_artifacts[artifact_path] = {
                    "bytecode": artifact["bytecode"]
                }
        return cls._contract_artifacts[artifact_path]

    @staticmethod
    def build_constructor_tx(
        w3: Web3,
        artifact: Dict,
        constructor_args: List[Any],
        tx_params: Optional[Dict] = None,
    ) -> Dict:
        """
        Build constructor transaction with proper arguments
        """
        constructor_types = [
            "address",  # platform address
            "uint256",  # skip
            "uint256",  # limit
        ]
        encoded_args = encode(constructor_types, constructor_args)
        data = artifact["bytecode"] + encoded_args.hex()

        default_params = {
            "from": "0x0000000000000000000000000000000000000000",
            "data": data,
            "gas": 30000000,
            "gasPrice": 0,
        }

        if tx_params:
            default_params.update(tx_params)

        return default_params

    @staticmethod
    def decode_campaign_data(result: bytes) -> List[CampaignData]:
        """
        Specific decoder for campaign data from BatchCampaignData contract
        """
        try:
            # Define the nested struct types
            campaign_struct = [
                "uint256",  # chainId
                "address",  # gauge
                "address",  # manager
                "address",  # rewardToken
                "uint8",  # numberOfPeriods
                "uint256",  # maxRewardPerVote
                "uint256",  # totalRewardAmount
                "uint256",  # totalDistributed
                "uint256",  # startTimestamp
                "uint256",  # endTimestamp
                "address",  # hook
            ]

            period_struct = [
                "uint256",  # rewardPerPeriod
                "uint256",  # rewardPerVote
                "uint256",  # leftover
                "bool",  # updated
            ]

            campaign_data_type = [
                "uint256",  # id
                f"({','.join(campaign_struct)})",  # campaign
                "bool",  # isClosed
                "bool",  # isWhitelistOnly
                "address[]",  # addresses
                f"({','.join(period_struct)})",  # currentPeriod
                "uint256",  # periodLeft
            ]

            full_type = f"({','.join(campaign_data_type)})[]"

            if len(result) % 32 != 0:
                result = result[: -(len(result) % 32)]

            raw_data = decode([full_type], result)[0]

            # Convert to typed dictionary
            return [
                CampaignData(
                    id=data[0],
                    campaign={
                        "chain_id": data[1][0],
                        "gauge": data[1][1],
                        "manager": data[1][2],
                        "reward_token": data[1][3],
                        "number_of_periods": data[1][4],
                        "max_reward_per_vote": data[1][5],
                        "total_reward_amount": data[1][6],
                        "total_distributed": data[1][7],
                        "start_timestamp": data[1][8],
                        "end_timestamp": data[1][9],
                        "hook": data[1][10],
                    },
                    is_closed=data[2],
                    is_whitelist_only=data[3],
                    addresses=data[4],
                    current_period={
                        "reward_per_period": data[5][0],
                        "reward_per_vote": data[5][1],
                        "leftover": data[5][2],
                        "updated": data[5][3],
                    },
                    period_left=data[6],
                )
                for data in raw_data
            ]

        except Exception as e:
            print(f"Error decoding campaign data: {str(e)}")
            print(f"Raw result (hex): {result.hex()}")
            raise

    @staticmethod
    def decode_result(types: List[str], result: bytes) -> Any:
        """Generic decoder for other contract calls"""
        return decode(types, result)
