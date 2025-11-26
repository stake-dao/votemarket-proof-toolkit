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

    function getRemainingPeriods(
        uint256 campaignId,
        uint256 epoch
    ) external view returns (uint256 periodsLeft);

    function getCampaign(uint256) external view returns (Campaign memory);

    function getCampaignUpgrade(
        uint256,
        uint256
    ) external view returns (CampaignUpgrade memory);

    function getAddressesByCampaign(
        uint256
    ) external view returns (address[] memory);

    function getPeriodPerCampaign(
        uint256 campaignId,
        uint256 epoch
    ) external view returns (Period memory);

    function currentEpoch() external view returns (uint256);

    function campaignCount() external view returns (uint256);

    function isClosedCampaign(uint256) external view returns (bool);

    function whitelistOnly(uint256) external view returns (bool);

    function EPOCH_LENGTH() external view returns (uint256);
}

contract BatchCampaignDataWithPeriods {
    struct PeriodData {
        uint256 epoch;
        IVotemarket.Period period;
    }
    
    struct CampaignData {
        uint256 id;
        IVotemarket.Campaign campaign;
        bool isClosed;
        bool isWhitelistOnly;
        address[] addresses;
        uint256 currentEpoch;
        uint256 remainingPeriods;
        PeriodData[] periods;
    }

    constructor(address platform, uint256 skip, uint256 limit) {
        IVotemarket votemarket = IVotemarket(platform);
        uint256 campaignCount = votemarket.campaignCount();
        
        // If limit is 0, use remaining campaigns from skip
        if (limit == 0) {
            require(skip < campaignCount, "Skip exceeds campaign count");
            limit = campaignCount - skip;
        }
        
        // Ensure limit doesn't exceed remaining campaigns
        uint256 remainingCampaigns = campaignCount - skip;
        limit = limit > remainingCampaigns ? remainingCampaigns : limit;
        
        // Create array of correct size
        CampaignData[] memory returnData = new CampaignData[](limit);
        
        // Fetch campaigns
        for (uint256 i = 0; i < limit; i++) {
            uint256 campaignId = skip + i;
            CampaignData memory c;
            c.id = campaignId;
            c.campaign = votemarket.getCampaign(campaignId);
            c.isClosed = votemarket.isClosedCampaign(campaignId);
            c.isWhitelistOnly = votemarket.whitelistOnly(campaignId);
            c.addresses = votemarket.getAddressesByCampaign(campaignId);

            uint256 currentEpoch = votemarket.currentEpoch();
            c.currentEpoch = currentEpoch;
            c.remainingPeriods = votemarket.getRemainingPeriods(campaignId, currentEpoch);

            // Check for latest upgrade
            uint256 checkedEpoch = currentEpoch;
            while (checkedEpoch > c.campaign.startTimestamp) {
                IVotemarket.CampaignUpgrade memory campaignUpgrade = votemarket
                    .getCampaignUpgrade(campaignId, checkedEpoch);
                // If an upgrade is found, add the latest upgrade
                if (campaignUpgrade.totalRewardAmount != 0) {
                    c.campaign.numberOfPeriods = campaignUpgrade
                        .numberOfPeriods;
                    c.campaign.totalRewardAmount = campaignUpgrade
                        .totalRewardAmount;
                    c.campaign.maxRewardPerVote = campaignUpgrade
                        .maxRewardPerVote;
                    c.campaign.endTimestamp = campaignUpgrade.endTimestamp;
                    break;
                }
                // else check the previous epoch
                checkedEpoch -= votemarket.EPOCH_LENGTH();
            }

            // Fetch periods for the campaign (only the actual campaign periods)
            uint256 epochLength = votemarket.EPOCH_LENGTH();
            
            // Handle campaigns that haven't started yet (future campaigns)
            if (c.campaign.startTimestamp > currentEpoch) {
                // No periods to fetch for future campaigns
                c.periods = new PeriodData[](0);
            } else {
                // Use the campaign's numberOfPeriods to determine how many to fetch
                uint256 periodsToFetch = c.campaign.numberOfPeriods;
                
                // Initialize periods array with exact number of campaign periods
                c.periods = new PeriodData[](periodsToFetch);
                
                // Fetch period data for each campaign period
                for (uint256 j = 0; j < periodsToFetch; j++) {
                    uint256 periodEpoch = c.campaign.startTimestamp + (j * epochLength);
                    c.periods[j] = PeriodData({
                        epoch: periodEpoch,
                        period: votemarket.getPeriodPerCampaign(campaignId, periodEpoch)
                    });
                }
            }

            returnData[i] = c;
        }

        bytes memory _data = abi.encode(returnData);
        // force constructor to return data via assembly
        assembly {
            // abi.encode adds an additional offset (32 bytes) that we need to skip
            let _dataStart := add(_data, 32)
            // Get the length of the encoded data from the bytes array
            let _dataLength := mload(_data)
            // Return the encoded data
            return(_dataStart, _dataLength)
        }
    }
}