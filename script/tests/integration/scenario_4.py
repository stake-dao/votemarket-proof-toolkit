"""Claim scenario : Create a campaign for sdCRV / CRV gauge, and skip to the reward week"""

from eth_utils import to_checksum_address
from proofs.main import VoteMarketProofs
from tests.integration.helpers.chain import (
    fast_forward,
    take_snapshot,
    restore_snapshot,
)
from tests.integration.helpers.vm import (
    setup,
    approve_erc20,
    create_campaign,
    insert_block_number,
    set_block_data,
    set_point_data,
    set_account_data,
    claim,
)
from shared.utils import get_closest_block_timestamp, get_rounded_epoch, load_json
from tests.integration.helpers.web3 import W3, get_latest_block
import json
import os

DAI = to_checksum_address("0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1")
DAI_WHALE = to_checksum_address("0x2d070ed1321871841245D8EE5B84bD2712644322")
ARB = to_checksum_address("0x912CE59144191C1204E64559FE8253a0e49E6548")
ARB_WHALE = to_checksum_address("0xF977814e90dA44bFA03b6295A0616a897441aceC")
GOV = to_checksum_address("0xE9847f18710ebC1c46b049e594c658B9412cba6e")
VOTEMARKET = to_checksum_address("0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e")

# Constants for the scenario
PROTOCOL = "curve"
GAUGE_ADDRESS = "0x26F7786de3E6D9Bd37Fcf47BE6F2bC455a21b74A"
GAUGE_ADDRESS_2 = "0xBE266d68Ce3dDFAb366Bb866F4353B6FC42BA43c"
USER_ADDRESS = "0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6"
CAMPAIGN_MANAGER = DAI_WHALE
CAMPAIGN_MANAGER_2 = ARB_WHALE
REWARD_TOKEN = DAI
REWARD_TOKEN_2 = ARB
NUMBER_OF_PERIODS = 4
MAX_REWARD_PER_VOTE = 100 * 10**18
TOTAL_REWARD_AMOUNT = 1000 * 10**18
WEEK = 7 * 24 * 60 * 60

def scenario_create():
    vm_proofs = VoteMarketProofs(1)
    snapshots = {}

    print(f"Running scenario: Create Campaign for {PROTOCOL} protocol")
    # Setup
    setup()
    snapshots["before_setup"] = take_snapshot()

    try:
        # Approve reward token
        snapshots["before_approve"] = take_snapshot()
        approve_erc20(REWARD_TOKEN, VOTEMARKET, TOTAL_REWARD_AMOUNT * 2, CAMPAIGN_MANAGER)
        approve_erc20(REWARD_TOKEN_2, VOTEMARKET, TOTAL_REWARD_AMOUNT, CAMPAIGN_MANAGER_2)
        # Create campaign
        snapshots["before_create_campaign"] = take_snapshot()
        create_campaign(
            gauge=GAUGE_ADDRESS,
            manager=CAMPAIGN_MANAGER,
            reward_token=REWARD_TOKEN,
            number_of_periods=NUMBER_OF_PERIODS,
            max_reward_per_vote=MAX_REWARD_PER_VOTE,
            total_reward_amount=TOTAL_REWARD_AMOUNT,
            addresses=["0x0000000000000000000000000000000000000000"],
            hook="0x0000000000000000000000000000000000000000",
            is_whitelist=False,
            from_address=CAMPAIGN_MANAGER,
        )

        create_campaign(
            gauge=GAUGE_ADDRESS,
            manager=CAMPAIGN_MANAGER_2,
            reward_token=REWARD_TOKEN_2,
            number_of_periods=NUMBER_OF_PERIODS,
            max_reward_per_vote=MAX_REWARD_PER_VOTE,
            total_reward_amount=TOTAL_REWARD_AMOUNT,
            addresses=["0x0000000000000000000000000000000000000000"],
            hook="0x0000000000000000000000000000000000000000",
            is_whitelist=False,
            from_address=CAMPAIGN_MANAGER_2,
        )

        create_campaign(
            gauge=GAUGE_ADDRESS_2,
            manager=CAMPAIGN_MANAGER,
            reward_token=REWARD_TOKEN,
            number_of_periods=NUMBER_OF_PERIODS,
            max_reward_per_vote=MAX_REWARD_PER_VOTE,
            total_reward_amount=TOTAL_REWARD_AMOUNT,
            addresses=["0x0000000000000000000000000000000000000000"],
            hook="0x0000000000000000000000000000000000000000",
            is_whitelist=False,
            from_address=CAMPAIGN_MANAGER,
        )

        # Increase time
        snapshots["before_fast_forward"] = take_snapshot()
        fast_forward(days=1)  # Skip next period

        # Get rounded epoch
        epoch = get_rounded_epoch(get_latest_block()["timestamp"])

        # Get nearest block for our current timestamp on Ethereum
        nearest_block = get_closest_block_timestamp("ethereum", epoch)

        # Get block data
        block_info = vm_proofs.get_block_info(nearest_block)

        # Insert block number
        snapshots["before_insert_block"] = take_snapshot()
        insert_block_number(
            epoch=epoch,
            block_number=block_info["block_number"],
            block_hash=block_info["block_hash"],
            block_timestamp=block_info["block_timestamp"],
            from_address=GOV,
        )
        """
        # Get proofs (gauge controller)
        print(f"Generating gauge controller proof for {PROTOCOL}")
        gauge_proofs = vm_proofs.get_gauge_proof(
            protocol=PROTOCOL,
            gauge_address=GAUGE_ADDRESS,
            current_epoch=epoch,
            block_number=block_info["block_number"],
        )

        gauge_proofs_2 = vm_proofs.get_gauge_proof(
            protocol=PROTOCOL,
            gauge_address=GAUGE_ADDRESS_2,
            current_epoch=epoch,
            block_number=block_info["block_number"],
        )
        

        # Set block data
        snapshots["before_set_block_data"] = take_snapshot()
        set_block_data(
            rlp_block_header=block_info["rlp_block_header"],
            controller_proof=gauge_proofs["gauge_controller_proof"],
            from_address=GOV,
        )
        # Set point data
        snapshots["before_set_point_data"] = take_snapshot()
        set_point_data(
            gauge=GAUGE_ADDRESS,
            epoch=epoch,
            storage_proof=gauge_proofs["point_data_proof"],
            from_address=GOV,
        )

        set_point_data(
            gauge=GAUGE_ADDRESS_2,
            epoch=epoch,
            storage_proof=gauge_proofs_2["point_data_proof"],
            from_address=GOV,
        )


        # Get proofs (user)
        user_proofs = vm_proofs.get_user_proof(
            protocol=PROTOCOL,
            gauge_address=GAUGE_ADDRESS,
            user=USER_ADDRESS,
            block_number=block_info["block_number"],
        )
        
        
        user_proofs_2 = vm_proofs.get_user_proof(
            protocol=PROTOCOL,
            gauge_address=GAUGE_ADDRESS_2,
            user=USER_ADDRESS,
            block_number=block_info["block_number"],
        )
        
        # Set user data
        snapshots["before_set_user_data"] = take_snapshot()
        set_account_data(
            account=USER_ADDRESS,
            gauge=GAUGE_ADDRESS,
            epoch=epoch,
            storage_proof=user_proofs["storage_proof"],
            from_address=GOV,
        )
        

        set_account_data(
            account=USER_ADDRESS,
            gauge=GAUGE_ADDRESS_2,
            epoch=epoch,
            storage_proof=user_proofs_2["storage_proof"],
            from_address=GOV,
        )
        """
        # Get rounded epoch
        epoch += WEEK
        fast_forward(days=7)

        # Get nearest block for our current timestamp on Ethereum
        nearest_block = get_closest_block_timestamp("ethereum", epoch)

        # Get block data
        block_info = vm_proofs.get_block_info(nearest_block)

        # Insert block number
        snapshots["before_insert_block"] = take_snapshot()
        insert_block_number(
            epoch=epoch,
            block_number=block_info["block_number"],
            block_hash=block_info["block_hash"],
            block_timestamp=block_info["block_timestamp"],
            from_address=GOV,
        )
        """
        # Get proofs (gauge controller)
        print(f"Generating gauge controller proof for {PROTOCOL}")
        gauge_proofs = vm_proofs.get_gauge_proof(
            protocol=PROTOCOL,
            gauge_address=GAUGE_ADDRESS,
            current_epoch=epoch,
            block_number=block_info["block_number"],
        )

        gauge_proofs_2 = vm_proofs.get_gauge_proof(
            protocol=PROTOCOL,
            gauge_address=GAUGE_ADDRESS_2,
            current_epoch=epoch,
            block_number=block_info["block_number"],
        )
        

        # Set block data
        snapshots["before_set_block_data"] = take_snapshot()
        set_block_data(
            rlp_block_header=block_info["rlp_block_header"],
            controller_proof=gauge_proofs["gauge_controller_proof"],
            from_address=GOV,
        )
        # Set point data
        snapshots["before_set_point_data"] = take_snapshot()
        set_point_data(
            gauge=GAUGE_ADDRESS,
            epoch=epoch,
            storage_proof=gauge_proofs["point_data_proof"],
            from_address=GOV,
        )

        set_point_data(
            gauge=GAUGE_ADDRESS_2,
            epoch=epoch,
            storage_proof=gauge_proofs_2["point_data_proof"],
            from_address=GOV,
        )


        # Get proofs (user)
        user_proofs = vm_proofs.get_user_proof(
            protocol=PROTOCOL,
            gauge_address=GAUGE_ADDRESS,
            user=USER_ADDRESS,
            block_number=block_info["block_number"],
        )
        
        
        user_proofs_2 = vm_proofs.get_user_proof(
            protocol=PROTOCOL,
            gauge_address=GAUGE_ADDRESS_2,
            user=USER_ADDRESS,
            block_number=block_info["block_number"],
        )
        
        # Set user data
        snapshots["before_set_user_data"] = take_snapshot()
        set_account_data(
            account=USER_ADDRESS,
            gauge=GAUGE_ADDRESS,
            epoch=epoch,
            storage_proof=user_proofs["storage_proof"],
            from_address=GOV,
        )
        

        set_account_data(
            account=USER_ADDRESS,
            gauge=GAUGE_ADDRESS_2,
            epoch=epoch,
            storage_proof=user_proofs_2["storage_proof"],
            from_address=GOV,
        )
        
        
        # Check reward token balance before claim
        reward_contract = W3.eth.contract(
            address=REWARD_TOKEN, abi=load_json("abi/erc20.json")
        )
        print(
            f"Reward token balance before claim: {reward_contract.functions.balanceOf(USER_ADDRESS).call()}"
        )

        # Claim
        snapshots["before_claim"] = take_snapshot()

        # Check reward token balance before claim
        votemarket = W3.eth.contract(
            address=VOTEMARKET, abi=load_json("abi/vm_platform.json")
        )
        
        print(votemarket.functions.totalClaimedByAccount(0, epoch, USER_ADDRESS).call())

        claim(
            campaign_id=0,
            account=USER_ADDRESS,
            epoch=epoch,
            hook_data="0x0000000000000000000000000000000000000000",
            from_address=CAMPAIGN_MANAGER,
        )

        # Check reward token balance after claim
        print(
            f"Reward token balance after claim: {reward_contract.functions.balanceOf(USER_ADDRESS).call()}"
        ) """

        print("Scenario completed.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        """
        # Save snapshots to a file
        file_dir = os.path.realpath(__file__)
        file_path = os.path.abspath(os.path.realpath(os.path.join(file_dir, '../temp/snapshots.json')))
        with open(file_path, 'w') as f:
            json.dump({k: v['result'] for k, v in snapshots.items()}, f)
        """
    print("Scenario completed. Snapshots saved.")


if __name__ == "__main__":
    scenario_create()