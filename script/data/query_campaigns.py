import os
from typing import List

from contracts.contract_reader import ContractReader
from eth_utils import to_checksum_address
from shared.constants import ContractRegistry, GlobalConstants
from shared.types import Campaign, Platform
from shared.web3_service import Web3Service


def get_all_platforms(protocol: str) -> List[Platform]:
    """
    Get all platform addresses for a given protocol across chains where it's deployed
    """
    try:
        # Get all chains where the protocol is deployed
        chains = ContractRegistry.get_chains(protocol.upper())

        return [
            {
                "protocol": protocol,
                "chain_id": chain_id,
                "address": ContractRegistry.get_address(
                    protocol.upper(), chain_id
                ),
            }
            for chain_id in chains
        ]
    except ValueError:
        return []


def query_active_campaigns(
    web3_service: Web3Service, chain_id: int, platform: str
) -> List[Campaign]:
    """
    Query active campaigns for a given chain + platform using multiple RPC calls in batches of 10
    """

    if chain_id not in web3_service.w3:
        web3_service.add_chain(chain_id, GlobalConstants.get_rpc_url(chain_id))

    platform = to_checksum_address(platform.lower())

    # Get the campaign count
    platform_contract = web3_service.get_contract(
        platform, "vm_platform", chain_id
    )
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
