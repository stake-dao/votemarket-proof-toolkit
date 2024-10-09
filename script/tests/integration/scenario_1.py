"""Claim scenario : Create a campaign for sdCRV / CRV gauge, and skip to the reward week"""

""" No block data bridged """

from web3 import Web3
from eth_utils import to_checksum_address
from external.vm_all_platforms import get_block_data
from proofs.main import VoteMarketProofs
from setup import setup, RPC_URL
from helpers import (
    approve_dai,
    create_campaign,
    insert_block_number,
    set_block_data,
    set_point_data,
    set_account_data,
    claim,
    increase_time,
    send_eth_to,
)
from shared.utils import get_closest_block_timestamp, get_rounded_epoch, load_json

DAI = to_checksum_address("0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1")
DAI_WHALE = to_checksum_address("0x2d070ed1321871841245D8EE5B84bD2712644322")
GOV = to_checksum_address("0xE9847f18710ebC1c46b049e594c658B9412cba6e")


def scenario_create(w3):
    """
    vm_proofs = VoteMarketProofs(1)

    print("Running scenario: Create Campaign")

    # Setup
    setup(w3)

    # Send ETH to accounts
    send_eth_to(w3, GOV, 5 * 10**18)
    send_eth_to(w3, DAI_WHALE, 5 * 10**18)

    # Approve DAI
    approve_dai(w3)

    # Create campaign
    create_campaign(
        w3,
        "0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A",  # gauge
        DAI_WHALE,  # manager
        DAI,  # reward_token
        4,  # number_of_periods
        100 * 10**18,  # max_reward_per_vote
        1000 * 10**18,  # total_reward_amount
        ["0x0000000000000000000000000000000000000000"],  # addresses
        "0x0000000000000000000000000000000000000000",  # hook
        False,  # is_whitelist
    )

    # Increase time
    increase_time(w3, 86400)  # Skip next period


    # Get rounded epoch
    epoch = get_rounded_epoch(w3.eth.get_block("latest").timestamp)

    # Get nearest block for our current timestamp on Ethereum
    nearest_block = get_closest_block_timestamp(
        "ethereum", epoch
    )

    # Get block data
    block_info = vm_proofs.get_block_info(nearest_block)

    # Insert block number
    insert_block_number(
        w3,
        epoch=epoch,
        block_number=block_info["block_number"],
        block_hash=block_info["block_hash"],
        block_timestamp=block_info["block_timestamp"],
    )

    # Get proofs (gauge controller)
    print(f"Generating gauge controller proof for curve")
    gauge_proofs = vm_proofs.get_gauge_proof(
        protocol="curve",
        gauge_address="0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A",
        current_epoch=epoch,
        block_number=block_info["block_number"],
    )


    print(f"Gauge proofs: {gauge_proofs}")

    # Set block data
    set_block_data(w3, block_info["rlp_block_header"], gauge_proofs["gauge_controller_proof"])


    set_point_data(w3, "0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A", epoch, gauge_proofs["point_data_proof"])


    # Get proofs (user)
    user_proofs = vm_proofs.get_user_proof(
        protocol="curve",
        gauge_address="0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A",
        user="0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6",
        block_number=block_info["block_number"],
    )

    # Set user data
    set_account_data(w3, "0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6", "0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A", epoch, user_proofs["storage_proof"])
    """

    dai_contract = w3.eth.contract(address=DAI, abi=load_json("abi/erc20.json"))

    print(f"DAI balance: {dai_contract.functions.balanceOf("0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6").call()}")

    claim(
        w3,
        0,
        "0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6",
        1727913600,
        "0x0000000000000000000000000000000000000000",
    )

    print(f"DAI balance: {dai_contract.functions.balanceOf("0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6").call()}")

    # Show campaign details
    votemarket_contract = w3.eth.contract(
        address=to_checksum_address("0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e"), abi=load_json("abi/vm_platform.json")
    )
    campaign = votemarket_contract.functions.campaignById(0).call()
    print(campaign)

    print('Current timestamp:', w3.eth.get_block("latest")["timestamp"])

    """
    # Read on Lens "getAccountVotes"
    lens_oracle_contract = w3.eth.contract(
        address=to_checksum_address("0xa20b142c2d52193e9de618dc694eba673410693f"), abi=load_json("abi/lens_oracle.json")
    )

    print(lens_oracle_contract.functions.getAccountVotes("0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6", "0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A", 1727913600).call())

    """
    print("Scenario completed.")


if __name__ == "__main__":
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    scenario_create(w3)
