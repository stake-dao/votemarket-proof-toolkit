// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

interface IOracle {
    struct VotedSlope {
        uint256 slope;
        uint256 end;
        uint256 lastVote;
        uint256 lastUpdate;
    }

    struct Point {
        uint256 bias;
        uint256 lastUpdate;
    }

    struct BlockHeader {
        bytes32 hash;
        bytes32 stateRootHash;
        uint256 number;
        uint256 timestamp;
    }

    function pointByEpoch(address gauge, uint256 epoch) external view returns (Point memory);
    function epochBlockNumber(uint256 epoch) external view returns (BlockHeader memory);
    function votedSlopeByEpoch(address account, address gauge, uint256 epoch)
        external
        view
        returns (VotedSlope memory);
}

// Get proofs for a set of gauges and users on the oracle for multiple epochs
// Passing oracle, gauge, users, and epochs array
contract GetInsertedProofs {
    struct EpochReturnData {
        uint256 epoch;
        bool is_block_updated;
        PointDataResult[] point_data_results;
        VotedSlopeDataResult[] voted_slope_data_results;
    }

    struct PointDataResult {
        address gauge;
        bool is_updated;
    }

    struct VotedSlopeDataResult {
        address account;
        address gauge;
        bool is_updated;
    }

    constructor(address oracle, address gauge, address[] memory users, uint256[] memory epochs) {
        // Initialize array for all epochs
        EpochReturnData[] memory epoch_results = new EpochReturnData[](epochs.length);

        // Process each epoch
        for (uint256 e = 0; e < epochs.length; e++) {
            uint256 target_period = epochs[e];

            // Initialize arrays with correct sizes for this epoch
            PointDataResult[] memory point_data_results = new PointDataResult[](1);
            VotedSlopeDataResult[] memory voted_slope_data_results = new VotedSlopeDataResult[](users.length);

            // Block header
            IOracle.BlockHeader memory block_header = IOracle(oracle).epochBlockNumber(target_period);

            // Point data
            IOracle.Point memory point = IOracle(oracle).pointByEpoch(gauge, target_period);
            point_data_results[0] = PointDataResult({
                gauge: gauge,
                is_updated: point.lastUpdate != 0
            });

            // Voted slope data
            for (uint256 i = 0; i < users.length; i++) {
                IOracle.VotedSlope memory voted_slope = IOracle(oracle).votedSlopeByEpoch(users[i], gauge, target_period);
                voted_slope_data_results[i] = VotedSlopeDataResult({
                    account: users[i],
                    gauge: gauge,
                    is_updated: voted_slope.lastUpdate != 0
                });
            }

            epoch_results[e] = EpochReturnData({
                epoch: target_period,
                is_block_updated: block_header.stateRootHash != bytes32(0),
                point_data_results: point_data_results,
                voted_slope_data_results: voted_slope_data_results
            });
        }

        bytes memory _data = abi.encode(epoch_results);
        assembly {
            let _dataStart := add(_data, 32)
            let _dataEnd := sub(msize(), _dataStart)
            return(_dataStart, _dataEnd)
        }
    }

    /// @notice Return the current period based on Gauge Controller rounding.
    function getCurrentPeriod() public view returns (uint256) {
        return (block.timestamp / 1 weeks) * 1 weeks;
    }
}