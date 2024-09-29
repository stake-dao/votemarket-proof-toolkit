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

    constructor(address platform, uint256 skip, uint256 limit) {
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

            uint256 currentEpoch = votemarket.currentEpoch();
            uint256 lastPeriod = c.isClosed
                ? c.campaign.endTimestamp
                : currentEpoch;
            c.currentPeriod = votemarket.getPeriodPerCampaign(i, lastPeriod);
            c.periodLeft = votemarket.getRemainingPeriods(i, currentEpoch);

            // Check for latest upgrade
            uint256 checkedEpoch = currentEpoch;
            while (checkedEpoch > c.campaign.startTimestamp) {
                IVotemarket.CampaignUpgrade memory campaignUpgrade = votemarket
                    .getCampaignUpgrade(i, checkedEpoch);
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
