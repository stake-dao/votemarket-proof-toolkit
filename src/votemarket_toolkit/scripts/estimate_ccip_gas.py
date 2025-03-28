import os
import json
import argparse
from web3 import Web3
from eth_abi import encode
from dotenv import load_dotenv
from typing import List, Tuple, Dict
import logging

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Contract ABIs
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

LAPOSTE_ABI = [
    {
        "inputs": [{"name": "chainId", "type": "uint256"}],
        "name": "sentNonces",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
        "stateMutability": "view"
    }
]

ADAPTER_ABI = [
    {
        "inputs": [{"name": "chainId", "type": "uint256"}],
        "name": "getBridgeChainId",
        "outputs": [{"name": "", "type": "uint64"}],
        "type": "function",
        "stateMutability": "view"
    },
    {
        "inputs": [{"name": "selector", "type": "uint64"}],
        "name": "getChainId",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
        "stateMutability": "view"
    }
]

TOKEN_FACTORY_ABI = [
    {
        "inputs": [{"name": "token", "type": "address"}],
        "name": "wrappedTokens",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function"
    }
]

BALANCE_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

# Chain-specific addresses
ROUTER_ADDRESSES = {
    # Chain ID -> Router Address
    42161: "0x141fa059441E0ca23ce184B6A78bafD2A517DdE8",  # Arbitrum
    1: "0x80226fc0Ee2b096224EeAc085Bb9a8cba1146f7D",      # Ethereum
}

# Move global Web3 instances to top level
source_w3 = None
destination_w3 = None

def initialize_web3_connections(source_rpc_url=None, destination_rpc_url=None):
    """Initialize Web3 connections for source and destination chains"""
    global source_w3, destination_w3
    
    if not source_rpc_url:
        source_rpc_url = os.getenv('ARBITRUM_MAINNET_RPC_URL')
        if not source_rpc_url:
            raise ValueError("No source RPC URL provided or found in environment")
    
    if not destination_rpc_url:
        destination_rpc_url = os.getenv('ETHEREUM_MAINNET_RPC_URL')
        if not destination_rpc_url:
            raise ValueError("No destination RPC URL provided or found in environment")
    
    source_w3 = Web3(Web3.HTTPProvider(source_rpc_url))
    destination_w3 = Web3(Web3.HTTPProvider(destination_rpc_url))
    
    return source_w3, destination_w3

def create_token_transfer(token_address: str, amount: int) -> Tuple[str, int]:
    """Create a token transfer tuple"""
    return (Web3.to_checksum_address(token_address), amount)

def fetch_token_metadata(token_address: str, w3: Web3) -> Tuple[str, str, int]:
    """Fetch token metadata directly from the contract"""
    token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    try:
        name = token_contract.functions.name().call()
        symbol = token_contract.functions.symbol().call()
        decimals = token_contract.functions.decimals().call()
        return (name, symbol, decimals)
    except Exception as e:
        logger.error(f"Error fetching metadata for token {token_address}: {str(e)}")
        return ("Unknown", "???", 18)

def get_chain_selector(adapter_address: str, chain_id: int, w3: Web3) -> int:
    """Get the chain selector from the adapter contract"""
    try:
        adapter_contract = w3.eth.contract(address=adapter_address, abi=ADAPTER_ABI)
        selector = adapter_contract.functions.getBridgeChainId(chain_id).call()
        logger.info(f"Chain selector for chain ID {chain_id}: {selector}")
        return selector
    except Exception as e:
        logger.error(f"Error getting chain selector: {str(e)}")
        raise

def get_chain_id_from_selector(adapter_address: str, selector: int, w3: Web3) -> int:
    """Get the chain ID from a selector using the adapter contract"""
    try:
        adapter_contract = w3.eth.contract(address=adapter_address, abi=ADAPTER_ABI)
        chain_id = adapter_contract.functions.getChainId(selector).call()
        logger.info(f"Chain ID for selector {selector}: {chain_id}")
        return chain_id
    except Exception as e:
        logger.error(f"Error getting chain ID from selector: {str(e)}")
        raise

def get_next_nonce(laposte_address: str, destination_chain_id: int) -> int:
    """Get the next nonce from LaPoste contract on the source chain"""
    try:
        laposte_contract = source_w3.eth.contract(address=laposte_address, abi=LAPOSTE_ABI)
        current_nonce = laposte_contract.functions.sentNonces(destination_chain_id).call()
        return current_nonce + 1
    except Exception as e:
        logger.error(f"Error getting nonce: {str(e)}")
        raise

def create_laposte_message(
    destination_chain_id: int,
    to_address: str,
    sender_address: str,
    tokens: List[Tuple[str, int]],
    nonce: int,
    payload: bytes = b''
) -> bytes:
    """Create and encode a Laposte message"""
    token_metadata = []
    formatted_tokens = []
    transfer_summary = []
    
    for token_address, amount in tokens:
        name, symbol, decimals = fetch_token_metadata(token_address, destination_w3)
        token_metadata.append((name, symbol, decimals))
        formatted_tokens.append((token_address, amount))
        
        human_amount = amount / (10 ** decimals)
        transfer_summary.append({
            'token': token_address,
            'symbol': symbol,
            'amount': human_amount,
            'raw_amount': amount
        })
    
    message_tuple = (
        destination_chain_id,
        to_address,
        sender_address,
        formatted_tokens,
        token_metadata,
        payload,
        nonce
    )
    
    # Store summary in global state for final recap
    global transfer_details
    transfer_details = {
        'to_address': to_address,
        'chain_id': destination_chain_id,
        'sender': sender_address,
        'transfers': transfer_summary,
        'nonce': nonce
    }

    return encode(
        ['(uint256,address,address,(address,uint256)[],(string,string,uint8)[],bytes,uint256)'],
        [message_tuple]
    )

def get_wrapped_token(token_address: str, token_factory_address: str) -> str:
    """Get the wrapped version of a token from the TokenFactory contract"""
    try:
        factory_contract = source_w3.eth.contract(address=token_factory_address, abi=TOKEN_FACTORY_ABI)
        wrapped_token = factory_contract.functions.wrappedTokens(token_address).call()
        return wrapped_token
    except Exception as e:
        logger.error(f"Error getting wrapped token: {str(e)}")
        raise

def get_token_balance(token_address: str, holder_address: str) -> int:
    """Get the token balance for a specific address"""
    try:
        token_contract = source_w3.eth.contract(address=token_address, abi=BALANCE_ABI)
        balance = token_contract.functions.balanceOf(holder_address).call()
        return balance
    except Exception as e:
        logger.error(f"Error getting token balance: {str(e)}")
        raise

def print_transfer_summary():
    """Print a summary of the transfer details"""
    if not hasattr(print_transfer_summary, 'transfer_details'):
        return
    
    details = transfer_details
    logger.info("\n=== Transfer Summary ===")
    logger.info(f"To: {details['to_address']}")
    logger.info(f"Chain ID: {details['chain_id']}")
    logger.info(f"Sender: {details['sender']}")
    logger.info(f"Nonce: {details['nonce']}")
    logger.info("\nTokens:")
    for t in details['transfers']:
        logger.info(f"- {t['amount']} {t['symbol']} ({t['token']})")

def estimate_ccip_fee(
    router_address: str,
    adapter_address: str,
    destination_chain_selector: int,
    message: bytes,
    gas_limit: int
) -> int:
    """
    Estimate CCIP fee for the cross-chain message
    Returns the fee in wei
    """
    try:
        # Load Router ABI from the resources file
        router_abi_path = "src/votemarket_toolkit/resources/abi/ccip_router.json"
        with open(router_abi_path, 'r') as f:
            ROUTER_ABI = json.load(f)

        router_contract = source_w3.eth.contract(
            address=router_address,
            abi=ROUTER_ABI
        )

        # Create EVM extra args with gas limit
        # This matches the Client._argsToBytes implementation in the Adapter contract
        EVM_EXTRA_ARGS_V1_TAG = bytes.fromhex('97a657c9')  # bytes4(keccak256("CCIP EVMExtraArgsV1"))
        
        # Encode EVMExtraArgsV1 struct
        extra_args_data = encode(['uint256'], [gas_limit])
        evm_extra_args = EVM_EXTRA_ARGS_V1_TAG + extra_args_data
        
        # Create the CCIP message struct according to the correct ABI structure
        ccip_message = {
            'receiver': encode(['address'], [adapter_address]),
            'data': message,
            'tokenAmounts': [],  # No tokens being transferred
            'feeToken': '0x0000000000000000000000000000000000000000',  # Using native token
            'extraArgs': evm_extra_args
        }

        # Get the fee from router
        fee = router_contract.functions.getFee(
            destination_chain_selector,
            ccip_message
        ).call()

        return fee
    except Exception as e:
        logger.error(f"Fee estimation failed: {str(e)}")
        raise

def simulate_ccip_receive(
    adapter_address: str,
    laposte_address: str,
    to_address: str,
    tokens: List[Tuple[str, int]],
) -> Dict:
    """
    Simulate CCIP receive and estimate gas and fee
    Returns a dictionary with gas estimate, buffer and required fee
    """
    # Arbitrum chain ID is 42161
    ARBITRUM_CHAIN_ID = 42161
    ETHEREUM_CHAIN_ID = 1
    
    # Get chain selector for source chain (Arbitrum)
    source_chain_selector = get_chain_selector(adapter_address, ARBITRUM_CHAIN_ID, destination_w3)
    
    # Get chain selector for destination chain (Ethereum)
    destination_chain_selector = get_chain_selector(adapter_address, ETHEREUM_CHAIN_ID, source_w3)

    # Get next nonce from LaPoste contract on source chain
    nonce = get_next_nonce(laposte_address, ETHEREUM_CHAIN_ID)

    # Create the Laposte message
    laposte_message = create_laposte_message(
        destination_chain_id=ETHEREUM_CHAIN_ID,
        to_address=to_address,
        sender_address=laposte_address,
        tokens=tokens,
        nonce=nonce
    )

    
    # Create Any2EVMMessage struct
    message = {
        'messageId': Web3.keccak(text='test'),
        'sourceChainSelector': source_chain_selector,
        'sender': encode(['address'], [laposte_address]),
        'data': laposte_message,
        'destTokenAmounts': []
    }
    
    # Create contract instance for gas estimation
    contract = destination_w3.eth.contract(
        address=adapter_address,
        abi=[{
            "inputs": [{
                "components": [
                    {"name": "messageId", "type": "bytes32", "internalType": "bytes32"},
                    {"name": "sourceChainSelector", "type": "uint64", "internalType": "uint64"},
                    {"name": "sender", "type": "bytes", "internalType": "bytes"},
                    {"name": "data", "type": "bytes", "internalType": "bytes"},
                    {
                        "name": "destTokenAmounts",
                        "type": "tuple[]",
                        "internalType": "struct Client.EVMTokenAmount[]",
                        "components": [
                            {"name": "token", "type": "address", "internalType": "address"},
                            {"name": "amount", "type": "uint256", "internalType": "uint256"}
                        ]
                    }
                ],
                "internalType": "struct Client.Any2EVMMessage",
                "name": "message",
                "type": "tuple"
            }],
            "name": "ccipReceive",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        }]
    )
    
    data = contract.encodeABI(fn_name='ccipReceive', args=[message])

    
    # Get router address for destination chain (Ethereum)
    DESTINATION_ROUTER_ADDRESS = ROUTER_ADDRESSES[1]  # Ethereum Mainnet
    
    print(f"DESTINATION_ROUTER_ADDRESS: {DESTINATION_ROUTER_ADDRESS}")


    try:
        gas = destination_w3.eth.estimate_gas({
            'from': DESTINATION_ROUTER_ADDRESS,
            'to': adapter_address,
            'data': data
        })

        # Remove Base Gas
        gas = gas - 50_000
        
        gas_with_buffer = int(gas * 1.077)  # Add 7.7% buffer
        
        # Print the transfer summary
        print_transfer_summary()
        
        logger.info("\n=== Gas Estimation ===")
        logger.info(f"Base gas: {gas:,}")
        logger.info(f"Gas with 7.7% buffer: {gas_with_buffer:,}")
        
        # After gas estimation, calculate CCIP fee
        BASE_GAS_LIMIT = 50_000  # Base gas limit from the Adapter contract
        total_gas_limit = gas_with_buffer + BASE_GAS_LIMIT
        
        # Get router address for source chain (Arbitrum)
        SOURCE_ROUTER_ADDRESS = ROUTER_ADDRESSES[42161]  # Arbitrum

        print(f"SOURCE_ROUTER_ADDRESS: {SOURCE_ROUTER_ADDRESS}")
        
        fee = estimate_ccip_fee(
            router_address=SOURCE_ROUTER_ADDRESS,
            adapter_address=adapter_address,
            destination_chain_selector=destination_chain_selector,  # Use destination chain selector
            message=laposte_message,
            gas_limit=total_gas_limit
        )

        # Add 2% buffer to the fee
        fee = int(fee * 1.02)

        # Add fee information to logs
        logger.info(f"CCIP Fee: {Web3.from_wei(fee, 'ether')} with 2% buffer")
        
        return {
            'base_gas': gas,
            'gas_with_buffer': gas_with_buffer,
            'ccip_fee': fee
        }
    except Exception as e:
        logger.error(f"Gas estimation failed: {str(e)}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Estimate CCIP gas for token transfers')
    parser.add_argument('--adapter', required=True, help='Adapter contract address')
    parser.add_argument('--laposte', required=True, help='LaPoste contract address')
    parser.add_argument('--to-address', required=True, help='Recipient address')
    parser.add_argument('--tokens', required=True, nargs='+', help='List of token addresses')
    parser.add_argument('--amounts', required=False, nargs='+', type=int, help='List of token amounts (optional)')
    parser.add_argument('--token-factory', default='0x96006425Da428E45c282008b00004a00002B345e', help='TokenFactory contract address')
    
    args = parser.parse_args()
    
    # Initialize Web3 connections
    initialize_web3_connections()
    
    # Convert addresses to checksum format
    args.adapter = Web3.to_checksum_address(args.adapter)
    args.laposte = Web3.to_checksum_address(args.laposte)
    args.to_address = Web3.to_checksum_address(args.to_address)
    args.token_factory = Web3.to_checksum_address(args.token_factory)
    args.tokens = [Web3.to_checksum_address(token) for token in args.tokens]
    
    # If amounts not provided, query balances of wrapped tokens
    if not args.amounts:
        amounts = []
        for token in args.tokens:
            wrapped_token = get_wrapped_token(token, args.token_factory)
            balance = get_token_balance(wrapped_token, args.to_address)
            amounts.append(balance)
        args.amounts = amounts
    elif len(args.tokens) != len(args.amounts):
        raise ValueError("Number of tokens must match number of amounts")
    
    tokens_with_amounts = list(zip(args.tokens, args.amounts))
    
    simulate_ccip_receive(
        adapter_address=args.adapter,
        laposte_address=args.laposte,
        to_address=args.to_address,
        tokens=tokens_with_amounts
    )

if __name__ == "__main__":
    main()
