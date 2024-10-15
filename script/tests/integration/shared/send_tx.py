import sys
from web3 import Web3
from eth_utils import to_checksum_address
from web3.gas_strategies.rpc import rpc_gas_price_strategy

# Connect to the local Anvil instance
W3 = Web3(Web3.HTTPProvider("http://localhost:8545"))
W3.eth.set_gas_price_strategy(rpc_gas_price_strategy)

def set_balance(address, balance):
    W3.provider.make_request("anvil_setBalance", [address, hex(balance)])

def impersonate_and_send_tx(from_address, to_address, calldata, value=0):
    from_address = to_checksum_address(from_address)
    to_address = to_checksum_address(to_address)

    # Ensure the sender has enough balance
    current_balance = W3.eth.get_balance(from_address)
    if current_balance < W3.to_wei(1, 'ether'):
        set_balance(from_address, W3.to_wei(10, 'ether'))

    try:
        W3.provider.make_request("anvil_impersonateAccount", [from_address])

        tx = {
            "from": from_address,
            "to": to_address,
            "data": calldata,
            "value": value,
            "gas": 2000000,
            "gasPrice": W3.eth.generate_gas_price(),
        }

        tx_hash = W3.eth.send_transaction(tx)
        tx_receipt = W3.eth.wait_for_transaction_receipt(tx_hash)

        print(f"Transaction successful. Hash: {tx_receipt.transactionHash.hex()}")
        print(f"Gas used: {tx_receipt.gasUsed}")
        return tx_receipt
    finally:
        W3.provider.make_request("anvil_stopImpersonatingAccount", [from_address])

if __name__ == "__main__":
    if len(sys.argv) != 4 and len(sys.argv) != 5:
        print("Usage: python send_tx.py <FROM_ADDRESS> <TO_ADDRESS> <CALLDATA> [VALUE]")
        sys.exit(1)

    from_address = sys.argv[1]
    to_address = sys.argv[2]
    calldata = sys.argv[3]
    value = int(sys.argv[4]) if len(sys.argv) == 5 else 0

    impersonate_and_send_tx(from_address, to_address, calldata, value)
