// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity 0.8.28;

import {BatchVerifier} from "src/verifiers/BatchVerifier.sol";
import {Oracle} from "src/oracle/Oracle.sol";
import {StateProofVerifier} from "src/utils/StateProofVerifier.sol";

interface Vm {
    function readFileBinary(string calldata path) external view returns (bytes memory);
    function warp(uint256 timestamp) external;
}

contract CurveProtocolTest {
    Vm internal constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    struct Fixture {
        bytes header;
        bytes accountProof;
        bytes32 storageRoot;
        address gauge;
        address user;
        bytes accountBag;
        bytes pointBag;
        uint256[4] expected;
        bytes32[3] accountPaths;
        bytes32 pointPath;
    }

    function checkExport(string memory filename) internal {
        Fixture memory f = abi.decode(vm.readFileBinary(filename), (Fixture));
        Oracle oracle = new Oracle(address(this));
        BatchVerifier verifier =
            new BatchVerifier(address(oracle), 0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB, 11, 9, 12, true);
        oracle.setAuthorizedBlockNumberProvider(address(this));
        oracle.setAuthorizedDataProvider(address(verifier));
        StateProofVerifier.BlockHeader memory h = StateProofVerifier.parseBlockHeader(f.header);
        uint256 epoch = h.timestamp / 1 weeks * 1 weeks;
        oracle.insertBlockNumber(epoch, h);
        verifier.registerStorageRoot(f.header, f.accountProof);
        require(verifier.storageRootByEpoch(epoch) == f.storageRoot, "controller storage root");

        {
            (bytes32 last, bytes32 slopePath, bytes32 endPath) = verifier.accountPaths(f.user, f.gauge);
            require(last == f.accountPaths[0], "lastVote path");
            require(slopePath == f.accountPaths[1], "slope path");
            require(endPath == f.accountPaths[2], "end path");
            require(verifier.pointPath(f.gauge, epoch) == f.pointPath, "point path");
        }

        vm.warp(h.timestamp + 1);
        address[] memory members = new address[](1);
        members[0] = f.user;
        verifier.setAccountDataBatch(f.gauge, epoch, members, f.accountBag);
        {
            (uint256 slope, uint256 end, uint256 lastVote, uint256 updated) =
                oracle.votedSlopeByEpoch(f.user, f.gauge, epoch);
            require(lastVote == f.expected[0] && lastVote > 0, "lastVote");
            require(slope == f.expected[1] && slope > 0, "slope");
            require(end == f.expected[2] && end > 0, "end");
            require(updated == h.timestamp + 1, "account timestamp");
        }

        members[0] = f.gauge;
        verifier.setPointDataBatch(members, epoch, f.pointBag);
        (uint256 bias, uint256 pointUpdated) = oracle.pointByEpoch(f.gauge, epoch);
        require(bias == f.expected[3] && bias > 0, "bias");
        require(pointUpdated == h.timestamp + 1, "point timestamp");
    }

    function testLowercaseCurve() public {
        checkExport("curve-0.abi");
    }

    function testUppercaseCurve() public {
        checkExport("curve-1.abi");
    }

    function testMixedCaseCurve() public {
        checkExport("curve-2.abi");
    }

    function testCurveWithWhitespace() public {
        checkExport("curve-3.abi");
    }
}
