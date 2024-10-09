"""Helper functions for Anvil integration test"""

from web3 import Web3
from eth_utils import to_checksum_address
from shared.utils import load_json

DAI = to_checksum_address("0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1")
DAI_WHALE = to_checksum_address("0x2d070ed1321871841245D8EE5B84bD2712644322")
VOTEMARKET = to_checksum_address("0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e")
ORACLE = to_checksum_address("0xa20b142c2d52193e9de618dc694eba673410693f")
VERIFIER = to_checksum_address("0x348d1bd2a18c9a93eb9ab8e5f55852da3036e225")
GOV = to_checksum_address("0xE9847f18710ebC1c46b049e594c658B9412cba6e")

def send_transaction(w3, contract_function, sender_address):
    tx = contract_function.build_transaction(
        {
            "from": sender_address,
            "nonce": w3.eth.get_transaction_count(sender_address),
            "gasPrice": w3.eth.generate_gas_price(),
        }
    )
    tx_hash = w3.eth.send_transaction(tx)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Transaction successful with hash: {tx_hash.hex()}")
    print(f"Gas used: {tx_receipt.gasUsed}")
    return tx_receipt


def impersonate_account(w3, address):
    w3.provider.make_request("anvil_impersonateAccount", [address])


def stop_impersonate_account(w3, address):
    w3.provider.make_request("anvil_stopImpersonatingAccount", [address])


def approve_dai(w3, amount=1000 * 10**18):
    impersonate_account(w3, DAI_WHALE)
    dai_contract = w3.eth.contract(address=DAI, abi=load_json("abi/erc20.json"))
    approve_function = dai_contract.functions.approve(VOTEMARKET, amount)
    send_transaction(w3, approve_function, DAI_WHALE)
    stop_impersonate_account(w3, DAI_WHALE)
    print(f"DAI approved: {amount}")


def create_campaign(
    w3,
    gauge,
    manager,
    reward_token,
    number_of_periods,
    max_reward_per_vote,
    total_reward_amount,
    addresses,
    hook,
    is_whitelist,
):
    impersonate_account(w3, DAI_WHALE)
    votemarket_contract = w3.eth.contract(
        address=VOTEMARKET, abi=load_json("abi/vm_platform.json")
    )
    create_campaign_function = votemarket_contract.functions.createCampaign(
        42161,
        gauge,
        manager,
        reward_token,
        number_of_periods,
        max_reward_per_vote,
        total_reward_amount,
        addresses,
        hook,
        is_whitelist,
    )
    tx_receipt = send_transaction(w3, create_campaign_function, DAI_WHALE)
    stop_impersonate_account(w3, DAI_WHALE)
    print("Campaign created.")
    return tx_receipt


def insert_block_number(w3, epoch, block_number, block_hash, block_timestamp):
    oracle_contract = w3.eth.contract(address=ORACLE, abi=load_json("abi/oracle.json"))
    impersonate_account(w3, GOV)
    insert_block_function = oracle_contract.functions.insertBlockNumber(
        epoch, (block_hash, "0x" + "0" * 64, block_number, block_timestamp)
    )
    tx_receipt = send_transaction(w3, insert_block_function, GOV)
    stop_impersonate_account(w3, GOV)
    print(f"Block number inserted for epoch {epoch}")
    return tx_receipt


def set_block_data(w3, rlp_block_header, controller_proof):
    verifier_contract = w3.eth.contract(
        address=VERIFIER, abi=load_json("abi/verifier.json")
    )
    impersonate_account(w3, GOV)
    set_block_data_function = verifier_contract.functions.setBlockData(
        rlp_block_header, controller_proof
    )
    tx_receipt = send_transaction(w3, set_block_data_function, GOV)
    stop_impersonate_account(w3, GOV)
    print("Block data set")
    return tx_receipt


def set_point_data(w3, gauge, epoch, storage_proof):
    verifier_contract = w3.eth.contract(
        address=VERIFIER, abi=load_json("abi/verifier.json")
    )
    impersonate_account(w3, GOV)
    set_point_data_function = verifier_contract.functions.setPointData(
        gauge, epoch, storage_proof
    )
    tx_receipt = send_transaction(w3, set_point_data_function, GOV)
    stop_impersonate_account(w3, GOV)
    print(f"Point data set for gauge {gauge} and epoch {epoch}")
    return tx_receipt


def set_account_data(w3, account, gauge, epoch, storage_proof):
    verifier_contract = w3.eth.contract(
        address=VERIFIER, abi=load_json("abi/verifier.json")
    )
    impersonate_account(w3, GOV)
    set_account_data_function = verifier_contract.functions.setAccountData(
        account, gauge, epoch, storage_proof
    )
    tx_receipt = send_transaction(w3, set_account_data_function, GOV)
    stop_impersonate_account(w3, GOV)
    print(f"Account data set for {account}, gauge {gauge}, and epoch {epoch}")
    return tx_receipt


def claim(w3, campaign_id, account, epoch, hook_data):
    votemarket_contract = w3.eth.contract(
        address=VOTEMARKET, abi=load_json("abi/vm_platform.json")
    )
    impersonate_account(w3, DAI_WHALE)
    claim_function = votemarket_contract.functions.claim(
        campaign_id, account, epoch, hook_data
    )
    tx_receipt = send_transaction(w3, claim_function, DAI_WHALE)
    stop_impersonate_account(w3, DAI_WHALE)
    print(
        f"Claim executed for campaign {campaign_id}, account {account}, and epoch {epoch}"
    )
    return tx_receipt


def increase_time(w3, seconds):
    w3.provider.make_request("evm_increaseTime", [seconds])
    w3.provider.make_request("evm_mine", [])
    print(f"Time increased by {seconds} seconds")


def send_eth_to(w3, address, amount):
    sender = {
        "private_key": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        "address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    }
    tx_hash = w3.eth.send_transaction(
        {"to": address, "from": sender["address"], "value": amount}
    )
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Sent {amount} wei to {address}")
    return tx_receipt
