import os
from web3 import Web3
from eth_abi import encode
from dotenv import load_dotenv
from typing import List, Tuple

load_dotenv()

# ERC20 ABI for metadata queries
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

def create_token_transfer(token_address: str, amount: int) -> Tuple[str, int]:
    """Create a token transfer tuple"""
    return (token_address, amount)

def fetch_token_metadata(token_address: str, w3: Web3) -> Tuple[str, str, int]:
    """Fetch token metadata directly from the contract"""
    token_contract = w3.eth.contract(address=w3.to_checksum_address(token_address), abi=ERC20_ABI)
    try:
        name = token_contract.functions.name().call()
        symbol = token_contract.functions.symbol().call()
        decimals = token_contract.functions.decimals().call()
        return (name, symbol, decimals)
    except Exception as e:
        print(f"Error fetching metadata for token {token_address}: {str(e)}")
        return ("Unknown", "???", 18)  # Default fallback

def create_laposte_message(
    destination_chain_id: int,
    to_address: str,
    sender_address: str,
    tokens: List[Tuple[str, int]] = None,
    w3: Web3 = None,
    nonce: int = 27,
    payload: bytes = b''
) -> bytes:
    """Create and encode a Laposte message"""
    if tokens is None:
        tokens = []
        
    # Fetch metadata for each token
    token_metadata = []
    if tokens and w3:
        for token_address, _ in tokens:
            metadata = fetch_token_metadata(token_address, w3)
            token_metadata.append(metadata)
        
    # Encode the Laposte Message struct
    message_tuple = (
        destination_chain_id,  # destinationChainId
        to_address,           # to
        sender_address,       # sender
        tokens,              # tokens array [(address, amount), ...]
        token_metadata,      # tokenMetadata array [(name, symbol, decimals), ...]
        payload,             # payload
        nonce                # nonce
    )
    
    # Encode the message struct using the correct format
    return encode(
        ['(uint256,address,address,(address,uint256)[],(string,string,uint8)[],bytes,uint256)'],
        [message_tuple]
    )

def simulate_ccip_receive(
    contract_address: str,
    sender_address: str,
    source_chain_selector: int,
    destination_chain_id: int,
    to_address: str,
    tokens: List[Tuple[str, int]] = None,
    rpc_url: str = os.getenv('ETHEREUM_MAINNET_RPC_URL')
) -> int:
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    # Create the Laposte message that will be the CCIP payload
    laposte_message = create_laposte_message(
        destination_chain_id=destination_chain_id,
        to_address=to_address,
        sender_address=sender_address,
        tokens=tokens,
        w3=w3
    )
    
    # Create Any2EVMMessage struct
    message = {
        'messageId': Web3.keccak(text='test'),  # MessageId corresponding to ccipSend on source
        'sourceChainSelector': source_chain_selector,  # Source chain selector
        'sender': encode(['address'], [sender_address]),  # abi.decode(sender) if coming from an EVM chain
        'data': laposte_message,  # The encoded Laposte message as payload
        'destTokenAmounts': []  # Keep CCIP token amounts empty as requested
    }
    
    # Encode function call with properly structured ABI matching the exact struct
    contract = w3.eth.contract(
        address=contract_address,
        abi=[{
            "inputs": [{
                "components": [
                    {
                        "name": "messageId",
                        "type": "bytes32",
                        "internalType": "bytes32"
                    },
                    {
                        "name": "sourceChainSelector",
                        "type": "uint64",
                        "internalType": "uint64"
                    },
                    {
                        "name": "sender",
                        "type": "bytes",
                        "internalType": "bytes"
                    },
                    {
                        "name": "data",
                        "type": "bytes",
                        "internalType": "bytes"
                    },
                    {
                        "name": "destTokenAmounts",
                        "type": "tuple[]",
                        "internalType": "struct Client.EVMTokenAmount[]",
                        "components": [
                            {
                                "name": "token",
                                "type": "address",
                                "internalType": "address"
                            },
                            {
                                "name": "amount",
                                "type": "uint256",
                                "internalType": "uint256"
                            }
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
    
    data = contract.encodeABI(
        fn_name='ccipReceive',
        args=[message]
    )
    
    # Impersonate the router address
    ROUTER_ADDRESS = "0x80226fc0Ee2b096224EeAc085Bb9a8cba1146f7D"
    
    # Estimate gas
    try:
        gas = w3.eth.estimate_gas({
            'from': ROUTER_ADDRESS,
            'to': contract_address,
            'data': data
        })
        
        return gas
    except Exception as e:
        print(f"Simulation failed: {str(e)}")
        return 0

if __name__ == "__main__":
    # Example usage
    adapter_address = "0xbF0000F5C600B1a84FE08F8d0013002ebC0064fe"
    laposte_address = "0xF0000058000021003E4754dCA700C766DE7601C2"
    source_chain = 4949039107694359620  # Arbitrum chain selector
    destination_chain = 1  # Ethereum chain ID
    to_address = "0x000755Fbe4A24d7478bfcFC1E561AfCE82d1ff62"  # Example recipient
    
    # Example token transfers with original amounts
    tokens = [
        create_token_transfer("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6333180229),  # USDC
        create_token_transfer("0x090185f2135308BaD17527004364eBcC2D37e5F6", 7473591157614707127492417),  # SPELL
        create_token_transfer("0x73968b9a57c6e53d41345fd57a6e6ae27d6cdb2f", 1904587375359549128349),  # SDT
        create_token_transfer("0x41d5d79431a913c4ae7d69a668ecdfe5ff9dfb68", 1236950706896935396717),  # INV
        create_token_transfer("0x30d20208d987713f46dfd34ef128bb16c404d10f", 458235312195510385492)  # SDT v2
    ]
    
    gas = simulate_ccip_receive(
        adapter_address,
        laposte_address,
        source_chain,
        destination_chain,
        to_address,
        tokens=tokens,
    )

    print(f"Estimated gas: {gas}")
    # Add 20% to the gas estimate
    gas = int(gas * 1.2)
    print(f"Estimated gas with 20% buffer: {gas}")
