from typing import TypedDict
from typing import List, Dict, Any
import logging

from shared.constants import GlobalConstants
from shared.web3_service import Web3Service
from w3multicall.multicall import W3Multicall

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)


class Campaign(TypedDict):
    chain_id: int
    gauge: str
    manager: str
    reward_token: str
    number_of_periods: int
    max_reward_per_vote: int
    total_reward_amount: int
    total_distributed: int
    start_timestamp: int
    end_timestamp: int
    hook: str


def query_active_campaigns(chain_id: int, platform: str) -> List[Dict[str, Any]]:
    """
    Query active campaigns for a given chain + platform
    """
    w3 = Web3Service(GlobalConstants.CHAIN_ID_TO_RPC[chain_id])
    platform_contract = w3.get_contract(platform, "vm_platform")

    # Multicall to get all active campaigns
    multicall = W3Multicall(w3)
    campaigns_count = platform_contract.functions.campaignCount().call()

    for i in range(campaigns_count):
        multicall.add(
            W3Multicall.Call(
                platform_contract.address, "isClosedCampaign(uint256)(bool)", [i]
            )
        )

    results = multicall.call()

    active_campaigns = [i for i, is_closed in enumerate(results) if not is_closed]

    multicall = W3Multicall(w3)
    for i in active_campaigns:
        multicall.add(
            W3Multicall.Call(
                platform_contract.address,
                "campaignById(uint256)((uint256,address,address,address,uint256,uint256,uint256,uint256,uint256,uint256,string))",
                [i],
            )
        )

    campaigns_data = multicall.call()

    active_gauges = [campaign["gauge"] for campaign in campaigns_data]

    return active_gauges


def get_all_platforms(arb_rpc_url: str) -> List[Dict[str, Any]]:
    """
    Get all platforms via Registry.
    """
    # TODO : Implement with real registry

    # Registry on Arbitrum
    w3_arbitrum = Web3Service(arb_rpc_url)
    registry = w3_arbitrum.get_contract(GlobalConstants.REGISTRY, "registry")

    # Get id 1
    campaign_id = 1
    campaign = registry.functions.campaignById(campaign_id).call()

    print(campaign)
