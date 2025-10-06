// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

interface ITokenFactory {
    function wrappedTokens(address) external view returns (address);
    function nativeTokens(address) external view returns (address);
}

contract GetTokensLaPoste {
    enum Mode {
        WRAPPED,    // Get wrapped tokens for native tokens
        NATIVE      // Get native tokens for wrapped tokens
    }

    constructor(address tokenFactory, address[] memory tokens, Mode mode) {
        address[] memory resultTokens = new address[](tokens.length);

        for (uint256 i = 0; i < tokens.length; i++) {
            if (mode == Mode.WRAPPED) {
                resultTokens[i] = ITokenFactory(tokenFactory).wrappedTokens(tokens[i]);
            } else {
                resultTokens[i] = ITokenFactory(tokenFactory).nativeTokens(tokens[i]);
            }
        }

        bytes memory _data = abi.encode(resultTokens);
        assembly {
            let _dataStart := add(_data, 32)
            let _dataEnd := sub(msize(), _dataStart)
            return(_dataStart, _dataEnd)
        }
    }
}