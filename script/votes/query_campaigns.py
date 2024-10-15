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
    web3_service: Web3Service, chain_id: int, platform: str
) -> List[Campaign]:
    """
    Query active campaigns for a given chain + platform using multiple RPC calls in batches of 10
    """

    if chain_id not in web3_service.w3:
        logging.info(f"Adding new chain to Web3 service: {chain_id}")
        web3_service.add_chain(chain_id, GlobalConstants.CHAIN_ID_TO_RPC[chain_id])

    print(platform)
    platform = to_checksum_address(platform.lower())

    # Get the campaign count
    platform_contract = web3_service.get_contract(platform, "vm_platform", chain_id)
    campaigns_count = platform_contract.functions.campaignCount().call()

    # Read the Solidity contract source
    contract_path = os.path.join(
        os.path.dirname(__file__), "..", "contracts", "BatchCampaigns.sol"
    )
    with open(contract_path, "r") as file:
        contract_source = file.read()

    formatted_campaigns: List[Campaign] = []
    batch_size = 10

    # Process campaigns in batches of 10
    for start_index in range(0, campaigns_count, batch_size):
        end_index = min(start_index + batch_size, campaigns_count)

        # Read contract data for the current batch
        result = ContractReader.read_contract_data(
            contract_source, [platform, start_index, end_index], chain_id
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
        for campaign in campaign_data:
            formatted_campaign: Campaign = {
                "id": campaign[0],
                "chain_id": campaign[1][0],
                "gauge": campaign[1][1],
                "listed_users": list(campaign[4]),
            }
            formatted_campaigns.append(formatted_campaign)

    return formatted_campaigns