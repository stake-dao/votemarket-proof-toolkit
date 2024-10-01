import os
from web3 import Web3
from eth_utils import to_checksum_address
from typing import List
import logging
from contracts.contract_reader import ContractReader
from shared.constants import GlobalConstants
from shared.types import Campaign, Platform
from shared.web3_service import Web3Service

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)


def get_all_platforms(protocol: str) -> List[Platform]:
    # Query on ARBITRUM registry all the platforms for the protocol

    # TODO once registry is ready

    return [
        {
            "protocol": "curve",
            "chain_id": 42161,
            "address": "0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e",
        }
    ]


def query_active_campaigns(
    w3_service: Web3Service, chain_id: int, platform: str
) -> List[Campaign]:
    """
    Query active campaigns for a given chain + platform using a single RPC call
    """

    platform = to_checksum_address(platform.lower())

    # Get the campaign count
    platform_contract = w3_service.get_contract(platform, "vm_platform", chain_id)
    campaigns_count = platform_contract.functions.campaignCount().call()

    # Read the Solidity contract source
    contract_path = os.path.join(
        os.path.dirname(__file__), "..", "contracts", "BatchCampaigns.sol"
    )
    with open(contract_path, "r") as file:
        contract_source = file.read()

    # Read contract data
    result = ContractReader.read_contract_data(
        contract_source, [platform, 0, campaigns_count], chain_id
    )

    # Decode the result
    campaign_data = ContractReader.decode_result(
        [
            "(uint256,("
            "uint256,address,address,address,uint8,uint256,uint256,uint256,uint256,uint256,address),"
            "bool,bool,address[],"
            "(uint256,uint256,uint256,bool),uint256)[]"
        ],
        result,
    )

    # Convert the decoded data to a more readable format
    formatted_campaigns: List[Campaign] = []

    for campaign in campaign_data:
        formatted_campaign: Campaign = {
            "id": campaign[0],
            "chain_id": campaign[1][0],
            "gauge": campaign[1][1],
            "blacklist": list(campaign[4]),
        }
        formatted_campaigns.append(formatted_campaign)

    return formatted_campaigns


def get_all_platforms(protocol: str) -> List[Platform]:
    """
    Get all platforms via Registry.
    """
    # TODO : Implement with real registry

    # Registry on Arbitrum
    w3_arbitrum = Web3Service(42161, GlobalConstants.CHAIN_ID_TO_RPC[42161])
    registry = w3_arbitrum.get_contract(GlobalConstants.REGISTRY, "registry")

    return [
        {"chain_id": 42161, "platform": "0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e"}
    ]
