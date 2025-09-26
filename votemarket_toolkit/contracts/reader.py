import json
from typing import Any, Dict, List, Optional, TypeVar

from eth_abi import decode, encode
from eth_utils import to_checksum_address

from votemarket_toolkit.campaigns.models import CampaignData

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
    def build_get_campaigns_constructor_tx(
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
    def build_get_campaigns_with_periods_constructor_tx(
        artifact: Dict,
        constructor_args: List[Any],
        tx_params: Optional[Dict] = None,
    ) -> Dict:
        """
        Build constructor transaction for BatchCampaignsWithPeriods contract
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
    def decode_campaign_data_with_periods(result: bytes) -> List[Dict]:
        """
        Decoder for campaign data from BatchCampaignsWithPeriods contract
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

            period_data_struct = [
                "uint256",  # epoch
                f"({','.join(period_struct)})",  # period
            ]

            campaign_data_type = [
                "uint256",  # id
                f"({','.join(campaign_struct)})",  # campaign
                "bool",  # isClosed
                "bool",  # isWhitelistOnly
                "address[]",  # addresses
                "uint256",  # currentEpoch
                "uint256",  # remainingPeriods
                f"({','.join(period_data_struct)})[]",  # periods array
            ]

            full_type = f"({','.join(campaign_data_type)})[]"

            if len(result) % 32 != 0:
                result = result[: -(len(result) % 32)]

            raw_data = decode([full_type], result)[0]

            # Convert to extended campaign data with all periods
            campaigns = []
            for data in raw_data:
                # Extract all periods
                periods = []
                for period_data in data[7]:
                    periods.append(
                        {
                            "timestamp": period_data[0],
                            "reward_per_period": period_data[1][0],
                            "reward_per_vote": period_data[1][1],
                            "leftover": period_data[1][2],
                            "updated": period_data[1][3],
                            "point_data_inserted": False,  # This would need to be checked separately
                        }
                    )

                campaigns.append(
                    {
                        "id": data[0],
                        "campaign": {
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
                        "is_closed": data[2],
                        "is_whitelist_only": data[3],
                        "addresses": data[4],
                        "current_epoch": data[5],
                        "remaining_periods": data[6],
                        "periods": periods,
                    }
                )

            return campaigns

        except Exception as e:
            print(f"Error decoding campaign data with periods: {str(e)}")
            print(f"Raw result (hex): {result.hex()}")
            raise

    @staticmethod
    def decode_result(types: List[str], result: bytes) -> Any:
        """Generic decoder for other contract calls"""
        return decode(types, result)

    @staticmethod
    def build_get_inserted_proofs_constructor_tx(
        artifact: Dict,
        oracle_address: str,
        gauge_address: str,
        user_addresses: List[str],
        epochs: List[int],
        tx_params: Optional[Dict] = None,
    ) -> Dict:
        """
        Build constructor transaction for GetInsertedProofs contract.

        Args:
            artifact: Contract artifact with bytecode
            oracle_address: Address of the Oracle contract
            gauge_address: Address of the gauge to query
            user_addresses: List of user addresses to check
            epochs: List of epochs to query
            tx_params: Optional transaction parameters

        Returns:
            Transaction dictionary ready for eth_call
        """
        constructor_types = [
            "address",  # oracle
            "address",  # gauge
            "address[]",  # users array
            "uint256[]",  # epochs array
        ]

        constructor_args = [
            to_checksum_address(oracle_address),
            to_checksum_address(gauge_address),
            [to_checksum_address(addr) for addr in user_addresses],
            epochs,
        ]

        encoded_args = encode(constructor_types, constructor_args)

        # Handle bytecode format
        bytecode = (
            artifact["bytecode"]["bytecode"]
            if isinstance(artifact["bytecode"], dict)
            else artifact["bytecode"]
        )
        data = bytecode + encoded_args.hex()

        default_params = {
            "from": "0x0000000000000000000000000000000000000000",
            "data": data,
            "gas": 10_000_000,  # Higher gas limit for multiple oracle calls
            "gasPrice": 0,
        }

        if tx_params:
            default_params.update(tx_params)

        return default_params

    @staticmethod
    def decode_inserted_proofs(result: bytes) -> List[Dict[str, Any]]:
        """
        Decode the result from GetInsertedProofs contract call.

        Returns a list of dictionaries, one for each epoch, with:
        - epoch: uint256
        - is_block_updated: bool
        - point_data_results: List of (gauge, is_updated) tuples
        - voted_slope_data_results: List of (account, gauge, is_updated) tuples
        """
        try:
            # Define the nested struct types for decoding
            point_data_result_type = "(address,bool)"  # (gauge, is_updated)
            voted_slope_data_result_type = (
                "(address,address,bool)"  # (account, gauge, is_updated)
            )

            epoch_return_data_type = f"(uint256,bool,{point_data_result_type}[],{voted_slope_data_result_type}[])"

            # Decode as array of EpochReturnData
            return_data_type = f"{epoch_return_data_type}[]"

            # Decode the result
            decoded = decode([return_data_type], result)[0]

            # Format the result for each epoch
            epoch_results = []
            for epoch_data in decoded:
                epoch_results.append(
                    {
                        "epoch": epoch_data[0],
                        "is_block_updated": epoch_data[1],
                        "point_data_results": [
                            {"gauge": point[0], "is_updated": point[1]}
                            for point in epoch_data[2]
                        ],
                        "voted_slope_data_results": [
                            {
                                "account": vote[0],
                                "gauge": vote[1],
                                "is_updated": vote[2],
                            }
                            for vote in epoch_data[3]
                        ],
                    }
                )

            return epoch_results

        except Exception as e:
            print(f"Error decoding inserted proofs result: {str(e)}")
            print(f"Raw result (hex): {result.hex()}")
            raise

    @staticmethod
    def build_get_ccip_fee_constructor_tx(
        artifact: Dict,
        router_address: str,
        dest_chain_selector: int,
        dest_chain_id: int,
        receiver: str,
        execution_gas_limit: int,
        tokens: List[Dict[str, Any]],
        payload: bytes,
        tx_params: Optional[Dict] = None,
    ) -> Dict:
        """
        Build constructor transaction for GetCCIPFee contract.
        """
        # Convert token list to the expected format
        formatted_tokens = [
            (to_checksum_address(token["tokenAddress"]), token["amount"])
            for token in tokens
        ]

        constructor_types = [
            "address",  # _router
            "uint64",  # _destChainSelector
            "uint256",  # _destChainId
            "address",  # _receiver
            "uint256",  # _executionGasLimit
            "(address,uint256)[]",  # _tokens array
            "bytes",  # _payload
        ]

        constructor_args = [
            router_address,
            dest_chain_selector,
            dest_chain_id,
            receiver,
            execution_gas_limit,
            formatted_tokens,
            payload,
        ]

        encoded_args = encode(constructor_types, constructor_args)
        # Access the bytecode string from the artifact
        data = (
            artifact["bytecode"]["bytecode"]
            if isinstance(artifact["bytecode"], dict)
            else artifact["bytecode"]
        )
        data = data + encoded_args.hex()

        default_params = {
            "from": "0x0000000000000000000000000000000000000000",
            "data": data,
            "gas": 500_000,
            "gasPrice": 0,
        }

        if tx_params:
            default_params.update(tx_params)

        return default_params
