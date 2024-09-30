import os
from web3 import Web3
from typing import List
import logging
from contracts.contract_reader import ContractReader
from shared.constants import GlobalConstants
from shared.types import Campaign, Platform
from shared.web3_service import Web3Service

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)


def query_active_campaigns(
    w3_service: Web3Service, chain_id: int, platform: str
) -> List[Campaign]:
    """
    Query active campaigns for a given chain + platform using a single RPC call
    """

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
    formatted_campaigns = []
    for campaign in campaign_data:
        formatted_campaign = {
            "id": campaign[0],
            "campaign": {
                "chainId": campaign[1][0],
                "gauge": campaign[1][1],
                "manager": campaign[1][2],
                "rewardToken": campaign[1][3],
                "numberOfPeriods": campaign[1][4],
                "maxRewardPerVote": campaign[1][5],
                "totalRewardAmount": campaign[1][6],
                "totalDistributed": campaign[1][7],
                "startTimestamp": campaign[1][8],
                "endTimestamp": campaign[1][9],
                "hook": campaign[1][10],
            },
            "isClosed": campaign[2],
            "isWhitelistOnly": campaign[3],
            "addresses": campaign[4],
            "currentPeriod": {
                "rewardPerPeriod": campaign[5][0],
                "rewardPerVote": campaign[5][1],
                "leftover": campaign[5][2],
                "updated": campaign[5][3],
            },
            "periodLeft": campaign[6],
        }
        formatted_campaigns.append(formatted_campaign)

    return formatted_campaigns


def get_all_platforms(arb_rpc_url: str) -> List[Platform]:
    """
    Get all platforms via Registry.
    """
    # TODO : Implement with real registry

    # Registry on Arbitrum
    w3_arbitrum = Web3Service(arb_rpc_url)
    registry = w3_arbitrum.get_contract(GlobalConstants.REGISTRY, "registry")

    return [{"chain_id": 42161, "platform": "0x0000000000000000000000000000000000"}]
