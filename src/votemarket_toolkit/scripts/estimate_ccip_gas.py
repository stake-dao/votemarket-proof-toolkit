import os
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

def create_token_transfer(token_address: str, amount: int) -> Tuple[str, int]:
    """Create a token transfer tuple"""
    w3 = Web3()
    return (w3.to_checksum_address(token_address), amount)

def fetch_token_metadata(token_address: str, w3: Web3) -> Tuple[str, str, int]:
    """Fetch token metadata directly from the contract"""
    checksummed_address = w3.to_checksum_address(token_address)
    token_contract = w3.eth.contract(address=checksummed_address, abi=ERC20_ABI)
    try:
        name = token_contract.functions.name().call()
        symbol = token_contract.functions.symbol().call()
        decimals = token_contract.functions.decimals().call()
        return (name, symbol, decimals)
    except Exception as e:
        logger.error(f"Error fetching metadata for token {checksummed_address}: {str(e)}")
        return ("Unknown", "???", 18)

def get_chain_selector(adapter_address: str, chain_id: int, w3: Web3) -> int:
    """Get the chain selector from the adapter contract"""
    try:
        checksummed_address = w3.to_checksum_address(adapter_address)
        adapter_contract = w3.eth.contract(address=checksummed_address, abi=ADAPTER_ABI)
        selector = adapter_contract.functions.getBridgeChainId(chain_id).call()
        return selector
    except Exception as e:
        logger.error(f"Error getting chain selector: {str(e)}")
        raise

def get_next_nonce(laposte_address: str, destination_chain_id: int, source_rpc_url: str) -> int:
    """Get the next nonce from LaPoste contract on the source chain"""
    try:
        w3 = Web3(Web3.HTTPProvider(source_rpc_url))
        checksummed_address = w3.to_checksum_address(laposte_address)
        laposte_contract = w3.eth.contract(address=checksummed_address, abi=LAPOSTE_ABI)
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
    w3: Web3,
    nonce: int,
    payload: bytes = b''
) -> bytes:
    """Create and encode a Laposte message"""
    checksummed_to = w3.to_checksum_address(to_address)
    checksummed_sender = w3.to_checksum_address(sender_address)
    
    token_metadata = []
    formatted_tokens = []
    transfer_summary = []
    
    for token_address, amount in tokens:
        checksummed_token = w3.to_checksum_address(token_address)
        name, symbol, decimals = fetch_token_metadata(checksummed_token, w3)
        token_metadata.append((name, symbol, decimals))
        formatted_tokens.append((checksummed_token, amount))
        
        # Store summary info
        human_amount = amount / (10 ** decimals)
        transfer_summary.append({
            'token': checksummed_token,
            'symbol': symbol,
            'amount': human_amount,
            'raw_amount': amount
        })
    
    message_tuple = (
        destination_chain_id,
        checksummed_to,
        checksummed_sender,
        formatted_tokens,
        token_metadata,
        payload,
        nonce
    )
    
    # Store summary in global state for final recap
    global transfer_details
    transfer_details = {
        'to_address': checksummed_to,
        'chain_id': destination_chain_id,
        'sender': checksummed_sender,
        'transfers': transfer_summary,
        'nonce': nonce
    }
    
    return encode(
        ['(uint256,address,address,(address,uint256)[],(string,string,uint8)[],bytes,uint256)'],
        [message_tuple]
    )

def get_wrapped_token(token_address: str, token_factory_address: str, w3: Web3) -> str:
    """Get the wrapped version of a token from the TokenFactory contract"""
    try:
        checksummed_token = w3.to_checksum_address(token_address)
        checksummed_factory = w3.to_checksum_address(token_factory_address)
        factory_contract = w3.eth.contract(address=checksummed_factory, abi=TOKEN_FACTORY_ABI)
        wrapped_token = factory_contract.functions.wrappedTokens(checksummed_token).call()
        return wrapped_token
    except Exception as e:
        logger.error(f"Error getting wrapped token: {str(e)}")
        raise

def get_token_balance(token_address: str, holder_address: str, w3: Web3) -> int:
    """Get the token balance for a specific address"""
    try:
        checksummed_token = w3.to_checksum_address(token_address)
        checksummed_holder = w3.to_checksum_address(holder_address)
        token_contract = w3.eth.contract(address=checksummed_token, abi=BALANCE_ABI)
        balance = token_contract.functions.balanceOf(checksummed_holder).call()
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

def simulate_ccip_receive(
    adapter_address: str,
    laposte_address: str,
    to_address: str,
    tokens: List[Tuple[str, int]],
    destination_rpc_url: str = None,
    source_rpc_url: str = None
) -> Dict:
    """
    Simulate CCIP receive and estimate gas
    Returns a dictionary with gas estimate and buffer
    """
    if not destination_rpc_url:
        destination_rpc_url = os.getenv('ETHEREUM_MAINNET_RPC_URL')
        if not destination_rpc_url:
            raise ValueError("No destination RPC URL provided or found in environment")
    
    if not source_rpc_url:
        source_rpc_url = os.getenv('ARBITRUM_MAINNET_RPC_URL')
        if not source_rpc_url:
            raise ValueError("No source RPC URL provided or found in environment")

    # Connect to destination chain (Ethereum)
    w3 = Web3(Web3.HTTPProvider(destination_rpc_url))
    
    # Arbitrum chain ID is 42161
    ARBITRUM_CHAIN_ID = 42161
    
    # Get chain selector from adapter
    source_chain_selector = get_chain_selector(adapter_address, ARBITRUM_CHAIN_ID, w3)
    
    # Get next nonce from LaPoste contract on source chain
    nonce = get_next_nonce(laposte_address, 1, source_rpc_url)  # 1 is Ethereum chain ID
    
    # Create the Laposte message
    laposte_message = create_laposte_message(
        destination_chain_id=1,  # Always Ethereum
        to_address=to_address,
        sender_address=laposte_address,
        tokens=tokens,
        w3=w3,
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
    contract = w3.eth.contract(
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
    
    # Router address for gas estimation
    ROUTER_ADDRESS = "0x80226fc0Ee2b096224EeAc085Bb9a8cba1146f7D"
    
    try:
        gas = w3.eth.estimate_gas({
            'from': ROUTER_ADDRESS,
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
        logger.info(f"Gas with 20% buffer: {gas_with_buffer:,}")
        
        return {
            'base_gas': gas,
            'gas_with_buffer': gas_with_buffer
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
    
    # Connect to Arbitrum for balance queries
    source_rpc_url = os.getenv('ARBITRUM_MAINNET_RPC_URL')
    if not source_rpc_url:
        raise ValueError("ARBITRUM_MAINNET_RPC_URL environment variable is required")
    
    source_w3 = Web3(Web3.HTTPProvider(source_rpc_url))
    
    # If amounts not provided, query balances of wrapped tokens
    if not args.amounts:
        amounts = []
        for token in args.tokens:
            wrapped_token = get_wrapped_token(token, args.token_factory, source_w3)
            balance = get_token_balance(wrapped_token, args.to_address, source_w3)
            amounts.append(balance)
        args.amounts = amounts
    elif len(args.tokens) != len(args.amounts):
        raise ValueError("Number of tokens must match number of amounts")
    
    tokens_with_amounts = list(zip(args.tokens, args.amounts))
    
    simulate_ccip_receive(
        adapter_address=args.adapter,
        laposte_address=args.laposte,
        to_address=args.to_address,
        tokens=tokens_with_amounts,
        source_rpc_url=source_rpc_url
    )

if __name__ == "__main__":
    main()
