import sys
from decimal import Decimal
from pathlib import Path

# Add the script directory to Python path
script_dir = str(Path(__file__).parent.parent.parent / "script")
sys.path.insert(0, script_dir)

from eth_utils import to_checksum_address
from votemarket_toolkit.utils import load_json
from votemarket_toolkit.shared.services.ccip_fee_service import CcipFeeService
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://ethereum.llamarpc.com"))

CCIP_ROUTER_ADDRESS = "0x80226fc0Ee2b096224EeAc085Bb9a8cba1146f7D"  # from https://docs.chain.link/ccip/directory/mainnet/chain/mainnet
MANAGER_ADDRESS = "0x8898502BA35AB64b3562aBC509Befb7Eb178D4df" # Example (Stake DAO Deployer)
CAMPAIGN_REMOTE_MANAGER_ADDRESS = "0x53aD4Cd1F1e52DD02aa9FC4A8250A1b74F351CA2"
HOOK_ADDRESS = "0x0000000000000000000000000000000000000000"


def create_campaign(
    chain_id: int,
    gauge_address: str,
    reward_token_address: str,
    number_of_periods: int,
    max_reward_per_vote: Decimal,
    total_reward_amount: Decimal,
) -> dict:
    """
    Creates a new campaign on the specified chain using the remote manager contract.

    Args:
        chain_id: Target chain ID
        gauge_address: Address of the gauge contract
        reward_token_address: Address of the reward token
        number_of_periods: Number of periods the campaign will run
        max_reward_per_vote: Maximum reward per vote (in token units)
        total_reward_amount: Total amount of rewards for the campaign (in token units)
    """
    fee_calculator = CcipFeeService(w3, CCIP_ROUTER_ADDRESS)

    # Initialize contract
    campaign_remote_manager_contract = w3.eth.contract(
        address=to_checksum_address(CAMPAIGN_REMOTE_MANAGER_ADDRESS),
        abi=load_json("src/votemarket_toolkit/resources/abi/campaign_remote_manager.json"),
    )

    # Convert decimal amounts to wei
    max_reward_per_vote_wei = w3.to_wei(max_reward_per_vote, "ether")
    total_reward_amount_wei = w3.to_wei(total_reward_amount, "ether")



    """
    const value =
      chainId === mainnet.id
        ? await getCcipFee({
            sourceChainId: mainnet.id,
            destChainId: arbitrum.id,
            executionGasLimit: 2_500_000,
            receiver: address,
            tokens: [
              {
                address: rewardToken.address,
                amount: formatUnits(parseUnits(totalRewardAmount, rewardToken.decimals), 0),
              },
            ],
          })
        : BigInt(0)
    """

    """
     [
                self.router_address,
                bridge_chain_id,
                chain_id,
                self.sender_address,
                1_000_000,
                [],
                additional_data,
            ]
    """


    # Using contract utils to get CCIP fee
    fee = fee_calculator.get_ccip_fee(
        dest_chain_id=chain_id,
        execution_gas_limit=2_500_000,
        receiver=to_checksum_address(MANAGER_ADDRESS),
        tokens=[
            {
                "address": reward_token_address,
                "amount": total_reward_amount_wei,
            },
        ],
        additional_data=b"",
    )

    # Build transaction with message value for CCIP fees
    campaign_params = {
        "chainId": chain_id,
        "gauge": to_checksum_address(gauge_address),
        "manager": to_checksum_address(MANAGER_ADDRESS),
        "rewardToken": to_checksum_address(reward_token_address),
        "numberOfPeriods": number_of_periods,
        "maxRewardPerVote": max_reward_per_vote_wei,
        "totalRewardAmount": total_reward_amount_wei,
        "addresses": [],  # Empty addresses array for blacklist/whitelist
        "hook": to_checksum_address(HOOK_ADDRESS),
        "isWhitelist": False,
    }

    tx = campaign_remote_manager_contract.functions.createCampaign(
        campaign_params,
        42161,  # Destination chain id
        550_000,  # Additional gas limit
    ).build_transaction(
        {
            "from": to_checksum_address(MANAGER_ADDRESS),
            "gas": 2000000,
            "value": fee,  # Using CCIP fee from client
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(MANAGER_ADDRESS),
        }
    )
    return tx

# Example usage
if __name__ == "__main__":
    tx = create_campaign(
        42161,
        "0x663fc22e92f26c377ddf3c859b560c4732ee639a",
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        4,
        0.01 * 10**6,
        100000 * 10**6,
    )
    print(tx)
