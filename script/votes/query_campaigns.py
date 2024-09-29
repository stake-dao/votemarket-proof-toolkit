from typing import TypedDict
from typing import List, Dict, Any
import logging
from solcx import compile_source
from eth_abi import decode
from shared.constants import GlobalConstants
from shared.web3_service import Web3Service, initialize_web3_service
from w3multicall.multicall import W3Multicall
from shared.web3_service import get_web3_service

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


def query_active_campaigns(chain_id: int, platform: str) -> List[str]:
    """
    Query active campaigns for a given chain + platform using a single RPC call
    """

    web3_service = get_web3_service()

    # Compile the CampaignDataRetriever contract
    contract_source = """
   // SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IVotemarket {
    struct Campaign {
        /// @notice Chain Id of the destination chain where the gauge is deployed.
        uint256 chainId;
        /// @notice Destination gauge address.
        address gauge;
        /// @notice Address to manage the campaign.
        address manager;
        /// @notice Main reward token.
        address rewardToken;
        /// @notice Duration of the campaign in weeks.
        uint8 numberOfPeriods;
        /// @notice Maximum reward per vote to distribute, to avoid overspending.
        uint256 maxRewardPerVote;
        /// @notice Total reward amount to distribute.
        uint256 totalRewardAmount;
        /// @notice Total reward amount distributed.
        uint256 totalDistributed;
        /// @notice Start timestamp of the campaign.
        uint256 startTimestamp;
        /// @notice End timestamp of the campaign.
        uint256 endTimestamp;
        /// Hook address.
        address hook;
    }

    struct CampaignUpgrade {
        /// @notice Number of periods after increase.
        uint8 numberOfPeriods;
        /// @notice Total reward amount after increase.
        uint256 totalRewardAmount;
        /// @notice New max reward per vote after increase.
        uint256 maxRewardPerVote;
        /// @notice New end timestamp after increase.
        uint256 endTimestamp;
    }

    struct Period {
        /// @notice Amount of reward reserved for the period.
        uint256 rewardPerPeriod;
        /// @notice Reward Per Vote.
        uint256 rewardPerVote;
        /// @notice  Leftover amount.
        uint256 leftover;
        /// @notice Flag to indicate if the period is updated.
        bool updated;
    }

    function getRemainingPeriods(uint256 campaignId, uint256 epoch) external view returns (uint256 periodsLeft);

    function getCampaign(uint256) external view returns (Campaign memory);

    function getCampaignUpgrade(uint256, uint256) external view returns (CampaignUpgrade memory);

    function getAddressesByCampaign(uint256) external view returns (address[] memory);

    function getPeriodPerCampaign(uint256 campaignId, uint256 epoch) external view returns (Period memory);

    function currentEpoch() external view returns (uint256);

    function campaignCount() external view returns (uint256);

    function isClosedCampaign(uint256) external view returns (bool);

    function whitelistOnly(uint256) external view returns (bool);

    function EPOCH_LENGTH() external view returns (uint256);
}

contract BatchCampaignData {

    struct CampaignData {
        uint256 id;
        IVotemarket.Campaign campaign;
        bool isClosed;
        bool isWhitelistOnly;
        address[] addresses;
        IVotemarket.Period currentPeriod;
        uint256 periodLeft;
    }

    constructor (address platform, uint256 skip, uint256 limit) {
        IVotemarket votemarket = IVotemarket(platform);
        limit = limit == 0 ? votemarket.campaignCount() : limit;

        CampaignData[] memory returnData = new CampaignData[](limit - skip);

        for (uint256 i = skip; i < limit; i++) {
            CampaignData memory c;

            c.id = i;
            c.campaign = votemarket.getCampaign(i);
            c.isClosed = votemarket.isClosedCampaign(i);
            c.isWhitelistOnly = votemarket.whitelistOnly(i);
            c.addresses = votemarket.getAddressesByCampaign(i);

            uint256 currentEpoch =  votemarket.currentEpoch();
            uint256 lastPeriod = c.isClosed ? c.campaign.endTimestamp : currentEpoch;
            c.currentPeriod = votemarket.getPeriodPerCampaign(i, lastPeriod);
            c.periodLeft = votemarket.getRemainingPeriods(i, currentEpoch);

            // Check for latest upgrade
            uint256 checkedEpoch = currentEpoch;
            while (checkedEpoch > c.campaign.startTimestamp) {
                IVotemarket.CampaignUpgrade memory campaignUpgrade = votemarket.getCampaignUpgrade(i, checkedEpoch);
                // If an upgrade is found, add the latest upgrade
                if (campaignUpgrade.totalRewardAmount != 0) {
                    c.campaign.numberOfPeriods = campaignUpgrade.numberOfPeriods;
                    c.campaign.totalRewardAmount = campaignUpgrade.totalRewardAmount;
                    c.campaign.maxRewardPerVote = campaignUpgrade.maxRewardPerVote;
                    c.campaign.endTimestamp = campaignUpgrade.endTimestamp;
                    break;
                }
                // else check the previous epoch
                checkedEpoch -= votemarket.EPOCH_LENGTH();
            }

            returnData[i - skip] = c;
        }

        bytes memory _data = abi.encode(returnData);
        // force constructor to return data via assembly
        assembly {
            // abi.encode adds an additional offset (32 bytes) that we need to skip
            let _dataStart := add(_data, 32)
            // msize() gets the size of active memory in bytes.
            // if we subtract msize() from _dataStart, the output will be
            // the amount of bytes from _dataStart to the end of memory
            // which due to how the data has been laid out in memory, will coincide with
            // where our desired data ends.
            let _dataEnd := sub(msize(), _dataStart)
            // starting from _dataStart, get all the data in memory.
            return(_dataStart, _dataEnd)
        }
    }
}
    """

    compiled_sol = compile_source(contract_source)
    contract_interface = compiled_sol["<stdin>:BatchCampaignData"]

    # Get the campaign count
    platform_contract = web3_service.get_contract(platform, "vm_platform", chain_id)
    campaigns_count = platform_contract.functions.campaignCount().call()

    # Deploy and call the contract
    result = web3_service.deploy_and_call_contract(
        contract_interface["abi"],
        contract_interface["bin"],
        [platform, 0, campaigns_count],
        chain_id,
    )

    print(result.hex())
    # Decode the result
    # The constructor returns an array of CampaignData structs
    campaign_data = decode(
        [
            "(uint256,("
            "uint256,address,address,address,uint8,uint256,uint256,uint256,uint256,uint256,address),"
            "bool,bool,address[],"
            "(uint256,uint256,uint256,bool),uint256)[]"
        ],
        result,
    )[0]

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
    print(formatted_campaigns)

    return formatted_campaigns  # Return the list of active campaigns


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

    return [{"chain_id": 42161, "platform": "0x0000000000000000000000000000000000"}]
