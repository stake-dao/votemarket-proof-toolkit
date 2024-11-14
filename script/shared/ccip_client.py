from eth_abi import encode
from eth_utils import to_checksum_address
from shared.utils import load_json
from web3 import Web3

CCIP_ADAPTER_ADDRESS = "0x4200740090f72e89302f001da5860000007d7ea7"
MANAGER_ADDRESS = "0x8898502BA35AB64b3562aBC509Befb7Eb178D4df"
CAMPAIGN_REMOTE_MANAGER_ADDRESS = "0xd1f0101Df22Cb7447F486Da5784237AB7a55eB4e"
HOOK_ADDRESS = "0x0000000000000000000000000000000000000000"


def encode_campaign_creation_message(
    w3: Web3,
    ccip_router_address: str,
    chain_id: int,
    gauge_address: str,
    reward_token_address: str,
    number_of_periods: int,
    max_reward_per_vote_wei: int,
    total_reward_amount_wei: int,
    gas_limit: int,
) -> tuple:

    # Step 0 : Get destination chain id
    adapter = w3.eth.contract(
        address=to_checksum_address(CCIP_ADAPTER_ADDRESS),
        abi=load_json("abi/ccip_adapter.json"),
    )
    bridge_chain_id = adapter.functions.getBridgeChainId(chain_id).call()

    # Step 1: Encode the campaign parameters
    campaign_params = encode(
        [
            "uint256",  # chainId
            "address",  # gauge
            "address",  # manager
            "address",  # rewardToken
            "uint8",  # numberOfPeriods
            "uint256",  # maxRewardPerVote
            "uint256",  # totalRewardAmount
            "address[]",  # addresses
            "address",  # hook
            "bool",  # isWhitelist
        ],
        [
            chain_id,
            to_checksum_address(gauge_address),
            to_checksum_address(MANAGER_ADDRESS),
            to_checksum_address(reward_token_address),
            number_of_periods,
            max_reward_per_vote_wei,
            total_reward_amount_wei,
            [],  # Empty addresses array
            to_checksum_address(HOOK_ADDRESS),
            False,
        ],
    )

    # Step 2: Encode the full payload with action type and sender
    payload = encode(
        [
            "uint8",  # ActionType
            "address",  # sender
            "bytes",  # parameters
        ],
        [
            0,  # ActionType.CREATE_CAMPAIGN = 0
            to_checksum_address(MANAGER_ADDRESS),
            campaign_params,
        ],
    )

    # Step 3: Create the CCIP message
    message = encode(
        [
            "uint256",  # destinationChainId
            "address",  # to
            "address",  # sender
            "(address,uint256)",  # token
            "(string,string,uint8)",  # tokenMetadata
            "bytes",  # payload
            "uint256",  # nonce
        ],
        [
            chain_id,
            CAMPAIGN_REMOTE_MANAGER_ADDRESS,
            MANAGER_ADDRESS,
            ("0x0000000000000000000000000000000000000000", 0),
            ("", "", 18),
            payload,  # Using our encoded payload here
            0,
        ],
    )

    # Step 4: Prepare final message components
    encoded_receiver = encode(["address"], [CAMPAIGN_REMOTE_MANAGER_ADDRESS])
    extra_args_selector = "0x97a657c9"
    encoded_extra_args = bytes.fromhex(extra_args_selector[2:]) + encode(
        ["uint256"], [gas_limit]
    )

    message_tuple = (
        encoded_receiver,  # receiver
        message,  # data
        [],  # token amounts
        "0x0000000000000000000000000000000000000000",  # fee token
        encoded_extra_args,  # extra args
    )

    router = w3.eth.contract(
        address=to_checksum_address(ccip_router_address),
        abi=load_json("abi/ccip_router.json"),
    )
    fee = router.functions.getFee(bridge_chain_id, message_tuple).call()

    return fee


def encode_campaign_management_message(
    w3: Web3,
    ccip_router_address: str,
    chain_id: int,
    campaign_id: int,
    reward_token_address: str,
    number_of_periods: int,
    total_reward_amount_wei: int,
    max_reward_per_vote_wei: int,
    gas_limit: int,
) -> tuple:
    """Encodes the campaign management message for CCIP"""

    # Step 0 : Get destination chain id
    adapter = w3.eth.contract(
        address=to_checksum_address(CCIP_ADAPTER_ADDRESS),
        abi=load_json("abi/ccip_adapter.json"),
    )
    bridge_chain_id = adapter.functions.getBridgeChainId(chain_id).call()

    # Step 1: Encode the management parameters
    management_params = encode(
        [
            "uint256",  # campaignId
            "address",  # rewardToken
            "uint8",  # numberOfPeriods
            "uint256",  # totalRewardAmount
            "uint256",  # maxRewardPerVote
        ],
        [
            campaign_id,
            to_checksum_address(reward_token_address),
            number_of_periods,
            total_reward_amount_wei,
            max_reward_per_vote_wei,
        ],
    )

    # Step 2: Encode the full payload with action type and sender
    payload = encode(
        [
            "uint8",  # ActionType
            "address",  # sender
            "bytes",  # parameters
        ],
        [
            1,  # ActionType.MANAGE_CAMPAIGN = 1
            to_checksum_address(MANAGER_ADDRESS),
            management_params,
        ],
    )

    # Step 3: Create the CCIP message
    message = encode(
        [
            "uint256",  # destinationChainId
            "address",  # to
            "address",  # sender
            "(address,uint256)",  # token
            "(string,string,uint8)",  # tokenMetadata
            "bytes",  # payload
            "uint256",  # nonce
        ],
        [
            chain_id,
            CAMPAIGN_REMOTE_MANAGER_ADDRESS,
            MANAGER_ADDRESS,
            ("0x0000000000000000000000000000000000000000", 0),
            ("", "", 18),
            payload,  # Using our encoded payload here
            0,
        ],
    )

    # Step 4: Prepare final message components
    encoded_receiver = encode(["address"], [CAMPAIGN_REMOTE_MANAGER_ADDRESS])
    extra_args_selector = "0x97a657c9"
    encoded_extra_args = bytes.fromhex(extra_args_selector[2:]) + encode(
        ["uint256"], [gas_limit]
    )

    message_tuple = (
        encoded_receiver,  # receiver
        message,  # data
        [],  # token amounts
        "0x0000000000000000000000000000000000000000",  # fee token
        encoded_extra_args,  # extra args
    )

    router = w3.eth.contract(
        address=to_checksum_address(ccip_router_address),
        abi=load_json("abi/ccip_router.json"),
    )
    fee = router.functions.getFee(bridge_chain_id, message_tuple).call()

    return fee
