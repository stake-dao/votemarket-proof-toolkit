from web3 import HTTPProvider, Web3
from web3.types import RPCResponse

BLOCKCHAIN_ADDRESS = "http://localhost:8545"
W3 = Web3(HTTPProvider(BLOCKCHAIN_ADDRESS))

# Constants
UNIT = 10**18
ETHER = 10**18
MASTER = W3.eth.accounts[0]
DUMMY = W3.eth.accounts[1]
ZERO_ADDRESS = "0x" + "0" * 40

last_accessed_account = 1


def check_error(resp: RPCResponse):
    if "error" in resp:
        raise Exception("rpc exception", resp["error"])


def fresh_account():
    global last_accessed_account
    last_accessed_account += 1
    try:
        return W3.eth.accounts[last_accessed_account]
    except IndexError:
        raise Exception(
            "Not enough accounts. Restart anvil with more accounts (e.g., anvil --accounts 500)"
        )


def fresh_accounts(num_accs):
    global last_accessed_account
    start = last_accessed_account + 1
    end = start + num_accs
    if end > len(W3.eth.accounts):
        raise Exception(
            "Not enough accounts. Restart anvil with more accounts (e.g., anvil --accounts 500)"
        )
    last_accessed_account = end - 1
    return W3.eth.accounts[start:end]


def get_eth_balance(account):
    return W3.eth.get_balance(account)


def get_latest_block():
    return W3.eth.get_block("latest")


def set_eth_balance(account, balance):
    check_error(
        W3.provider.make_request("anvil_setBalance", [account, balance])
    )


def send_value(sender, recipient, value):
    tx_hash = W3.eth.send_transaction(
        {"from": sender, "to": recipient, "value": value}
    )
    return W3.eth.wait_for_transaction_receipt(tx_hash)


def force_mine_block():
    check_error(W3.provider.make_request("evm_mine", []))


def impersonate_account(address):
    check_error(
        W3.provider.make_request("anvil_impersonateAccount", [address])
    )


def stop_impersonate_account(address):
    check_error(
        W3.provider.make_request("anvil_stopImpersonatingAccount", [address])
    )


def send_transaction(contract_function, sender_address):
    impersonate_account(sender_address)
    tx = contract_function.build_transaction(
        {
            "from": sender_address,
            "nonce": W3.eth.get_transaction_count(sender_address),
            "gasPrice": W3.eth.generate_gas_price(),
        }
    )
    tx_hash = W3.eth.send_transaction(tx)
    tx_receipt = W3.eth.wait_for_transaction_receipt(tx_hash)
    stop_impersonate_account(sender_address)
    print(f"Transaction successful with hash: {tx_hash.hex()}")
    print(f"Gas used: {tx_receipt.gasUsed}")
    return tx_receipt
