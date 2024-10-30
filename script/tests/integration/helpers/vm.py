from shared.utils import load_json
from eth_utils import to_checksum_address
from .web3 import (
    W3,
    get_eth_balance,
    impersonate_account,
    send_transaction,
    send_value,
    set_eth_balance,
    stop_impersonate_account,
    fresh_account,
)
from web3.gas_strategies.rpc import rpc_gas_price_strategy

# Constants
VOTEMARKET = to_checksum_address("0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e")
ORACLE = to_checksum_address("0xa20b142c2d52193e9de618dc694eba673410693f")
VERIFIER = to_checksum_address("0x348d1bd2a18c9a93eb9ab8e5f55852da3036e225")
GOV = to_checksum_address("0xE9847f18710ebC1c46b049e594c658B9412cba6e")


def setup():
    W3.eth.set_gas_price_strategy(rpc_gas_price_strategy)

    set_eth_balance(GOV, hex(100 * 10**18))

    impersonate_account(GOV)
    oracle_contract = W3.eth.contract(
        address=ORACLE, abi=load_json("abi/oracle.json")
    )
    send_transaction(
        oracle_contract.functions.setAuthorizedDataProvider(VERIFIER), GOV
    )
    send_transaction(
        oracle_contract.functions.setAuthorizedBlockNumberProvider(VERIFIER),
        GOV,
    )
    send_transaction(
        oracle_contract.functions.setAuthorizedBlockNumberProvider(GOV), GOV
    )

    stop_impersonate_account(GOV)

    print("Setup completed.")


def approve_erc20(token_address, spender, amount, from_address):
    erc20_contract = W3.eth.contract(
        address=token_address, abi=load_json("abi/erc20.json")
    )
    approve_function = erc20_contract.functions.approve(spender, amount)
    tx_receipt = send_transaction(approve_function, from_address)
    print(f"Token {token_address} approved: {amount} for spender {spender}")
    return tx_receipt


def create_campaign(
    gauge,
    manager,
    reward_token,
    number_of_periods,
    max_reward_per_vote,
    total_reward_amount,
    addresses,
    hook,
    is_whitelist,
    from_address,
):
    votemarket_contract = W3.eth.contract(
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
    tx_receipt = send_transaction(create_campaign_function, from_address)
    print("Campaign created.")
    return tx_receipt


def insert_block_number(
    epoch, block_number, block_hash, block_timestamp, from_address
):
    oracle_contract = W3.eth.contract(
        address=ORACLE, abi=load_json("abi/oracle.json")
    )
    insert_block_function = oracle_contract.functions.insertBlockNumber(
        epoch, (block_hash, "0x" + "0" * 64, block_number, block_timestamp)
    )
    tx_receipt = send_transaction(insert_block_function, from_address)
    print(f"Block number {block_number} inserted for epoch {epoch}")
    return tx_receipt


def set_block_data(rlp_block_header, controller_proof, from_address):
    verifier_contract = W3.eth.contract(
        address=VERIFIER, abi=load_json("abi/verifier.json")
    )
    set_block_data_function = verifier_contract.functions.setBlockData(
        rlp_block_header, controller_proof
    )
    tx_receipt = send_transaction(set_block_data_function, from_address)
    print("Block data set")
    return tx_receipt


def set_point_data(gauge, epoch, storage_proof, from_address):
    verifier_contract = W3.eth.contract(
        address=VERIFIER, abi=load_json("abi/verifier.json")
    )
    set_point_data_function = verifier_contract.functions.setPointData(
        gauge, epoch, storage_proof
    )
    tx_receipt = send_transaction(set_point_data_function, from_address)
    print(f"Point data set for gauge {gauge} and epoch {epoch}")
    return tx_receipt


def set_account_data(account, gauge, epoch, storage_proof, from_address):
    verifier_contract = W3.eth.contract(
        address=VERIFIER, abi=load_json("abi/verifier.json")
    )
    set_account_data_function = verifier_contract.functions.setAccountData(
        account, gauge, epoch, storage_proof
    )
    tx_receipt = send_transaction(set_account_data_function, from_address)
    print(f"Account data set for {account}, gauge {gauge}, and epoch {epoch}")
    return tx_receipt


def claim(campaign_id, account, epoch, hook_data, from_address):
    votemarket_contract = W3.eth.contract(
        address=VOTEMARKET, abi=load_json("abi/vm_platform.json")
    )
    claim_function = votemarket_contract.functions.claim(
        campaign_id, account, epoch, hook_data
    )
    tx_receipt = send_transaction(claim_function, from_address)
    print(
        f"Claim executed for campaign {campaign_id}, account {account}, and epoch {epoch}"
    )
    return tx_receipt
