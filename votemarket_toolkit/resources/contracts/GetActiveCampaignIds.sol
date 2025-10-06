// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IVMPlatform {
    function campaignCount() external view returns (uint256);
    function isClosedCampaign(uint256 campaignId) external view returns (bool);
    function getRemainingPeriods(uint256 campaignId, uint256 currentEpoch) external view returns (uint256);
    function currentEpoch() external view returns (uint256);
}

/**
 * @title GetActiveCampaignIds
 * @notice Efficiently fetches active campaign IDs from a VoteMarket platform
 * @dev This contract is deployed temporarily to batch check campaign statuses
 */
contract GetActiveCampaignIds {
    struct ActiveCampaignBatch {
        uint256[] campaignIds;
        uint256 totalChecked;
        uint256 totalActive;
    }

    /**
     * @notice Constructor that checks a range of campaigns and returns active ones
     * @param platform The VoteMarket platform address
     * @param startId The starting campaign ID (inclusive)
     * @param limit Maximum number of campaigns to check (use large number for all)
     */
    constructor(
        address platform,
        uint256 startId,
        uint256 limit
    ) {
        IVMPlatform vmPlatform = IVMPlatform(platform);
        
        uint256 currentEpoch = vmPlatform.currentEpoch();
        uint256 campaignCount = vmPlatform.campaignCount();
        
        // Calculate actual range to check
        uint256 endId = startId + limit;
        if (endId > campaignCount) {
            endId = campaignCount;
        }
        
        // Count active campaigns first to allocate array
        uint256 activeCount = 0;
        for (uint256 i = startId; i < endId; i++) {
            if (!vmPlatform.isClosedCampaign(i)) {
                uint256 remaining = vmPlatform.getRemainingPeriods(i, currentEpoch);
                if (remaining > 0) {
                    activeCount++;
                }
            }
        }
        
        // Now collect the active campaign IDs
        uint256[] memory activeCampaignIds = new uint256[](activeCount);
        uint256 index = 0;
        
        for (uint256 i = startId; i < endId; i++) {
            if (!vmPlatform.isClosedCampaign(i)) {
                uint256 remaining = vmPlatform.getRemainingPeriods(i, currentEpoch);
                if (remaining > 0) {
                    activeCampaignIds[index] = i;
                    index++;
                }
            }
        }
        
        // Return data via assembly
        bytes memory returnData = abi.encode(ActiveCampaignBatch({
            campaignIds: activeCampaignIds,
            totalChecked: endId - startId,
            totalActive: activeCount
        }));
        
        assembly {
            return(add(returnData, 0x20), mload(returnData))
        }
    }
}