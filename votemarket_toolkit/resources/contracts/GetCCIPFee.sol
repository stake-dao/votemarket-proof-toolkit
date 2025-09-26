// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

interface ICcipRouter {
    struct EVMExtraArgsV1 {
        uint256 gasLimit;
    }

    struct EVMTokenAmount {
        address token; // token address on the local chain.
        uint256 amount; // Amount of tokens.
    }

    struct EVM2AnyMessage {
        bytes receiver; // abi.encode(receiver address) for dest EVM chains
        bytes data; // Data payload
        EVMTokenAmount[] tokenAmounts; // Token transfers
        address feeToken; // Address of feeToken. address(0) means you will send msg.value.
        bytes extraArgs; // Populate this with _argsToBytes(EVMExtraArgsV2)
    }

    function getFee(uint64 destinationChainSelector, EVM2AnyMessage memory message) external view returns (uint256 fee);
}

interface ILaPoste {
    struct Token {
        address tokenAddress;
        uint256 amount;
    }

    struct TokenMetadata {
        string name;
        string symbol;
        uint8 decimals;
    }

    struct MessageParams {
        uint256 destinationChainId;
        address to;
        Token[] tokens;
        bytes payload;
    }

    struct Message {
        uint256 destinationChainId;
        address to;
        address sender;
        Token[] tokens;
        TokenMetadata[] tokenMetadata;
        bytes payload;
        uint256 nonce;
    }

    function sentNonces(uint256 destChainId) external view returns (uint256);
}

contract GetCCIPFee {
    bytes4 constant EVM_EXTRA_ARGS_V1_TAG = 0x97a657c9;

    address constant LA_POSTE = 0xF0000058000021003E4754dCA700C766DE7601C2;

    constructor(address _router, uint64 _destChainSelector, uint256 _destChainId, address _receiver, uint256 _executionGasLimit, ILaPoste.Token[] memory _tokens, bytes memory _payload) {
        ILaPoste.Message memory message;

        message.destinationChainId = _destChainId;
        message.to = _receiver;
        message.sender = msg.sender;
        message.payload = _payload;

        message.nonce = ILaPoste(LA_POSTE).sentNonces(_destChainId) + 1;
        message.tokens = new ILaPoste.Token[](_tokens.length);
        message.tokenMetadata = new ILaPoste.TokenMetadata[](_tokens.length);

        for (uint256 i = 0; i < _tokens.length; i++) {
            if (_tokens[i].tokenAddress != address(0)) {
                message.tokens[i] = _tokens[i];

                ILaPoste.TokenMetadata memory metadata;
                metadata.name = "LaPoste Votemarket Bridge";
                metadata.symbol = "pVmBridge";
                metadata.decimals = 18;

                message.tokenMetadata[i] = metadata;
            }
        }

        uint256 totalGasLimit = _executionGasLimit + 50000;

        ICcipRouter.EVMExtraArgsV1 memory evmExtraArgs = ICcipRouter.EVMExtraArgsV1({gasLimit: totalGasLimit});

        ICcipRouter.EVM2AnyMessage memory ccipMessage = ICcipRouter.EVM2AnyMessage({
            receiver: abi.encode(_receiver),
            data: abi.encode(message),
            tokenAmounts: new ICcipRouter.EVMTokenAmount[](0),
            feeToken: address(0),
            extraArgs: abi.encodeWithSelector(EVM_EXTRA_ARGS_V1_TAG, evmExtraArgs)
        });


        uint256 fee = ICcipRouter(_router).getFee(_destChainSelector, ccipMessage);

        bytes memory _data = abi.encode(fee);
        assembly {
            let _dataStart := add(_data, 32)
            let _dataEnd := sub(msize(), _dataStart)
            return(_dataStart, _dataEnd)
        }
    }
}