"""Setup for Anvil integration test"""

from web3 import Web3
from eth_utils import to_checksum_address
from dotenv import load_dotenv
from web3.gas_strategies.rpc import rpc_gas_price_strategy

from shared.utils import load_json
from helpers import send_transaction, impersonate_account, stop_impersonate_account, send_eth_to

load_dotenv()

# Constants
RPC_URL = "http://127.0.0.1:8545"

""" ARBITRUM """
DAI = to_checksum_address("0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1")
DAI_WHALE = to_checksum_address("0x2d070ed1321871841245D8EE5B84bD2712644322")
ORACLE = to_checksum_address("0xa20b142c2d52193e9de618dc694eba673410693f")
VERIFIER = to_checksum_address("0x348d1bd2a18c9a93eb9ab8e5f55852da3036e225")
VOTEMARKET = to_checksum_address("0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e")
LENS_ORACLE = to_checksum_address("0xc65973c048fad0327a24c40848991c0fccbd3279")
GOV = to_checksum_address("0xE9847f18710ebC1c46b049e594c658B9412cba6e")
TEST_ADDRESS = to_checksum_address("0xE9847f18710ebC1c46b049e594c658B9412cba6e")

def setup(w3):
    # Setup (send funs to GOV, and Test addresses)
    send_eth_to(w3, GOV, 5 * 10**18)
    send_eth_to(w3, DAI_WHALE, 5 * 10**18)
    send_eth_to(w3, TEST_ADDRESS, 5 * 10**18)

    impersonate_account(w3, GOV)
    oracle_contract = w3.eth.contract(address=ORACLE, abi=load_json("abi/oracle.json"))
    w3.eth.set_gas_price_strategy(rpc_gas_price_strategy)

    transactions = [
        oracle_contract.functions.setAuthorizedDataProvider(VERIFIER),
        oracle_contract.functions.setAuthorizedBlockNumberProvider(VERIFIER),
        oracle_contract.functions.setAuthorizedBlockNumberProvider(GOV),
    ]

    for transaction in transactions:
        send_transaction(w3, transaction, GOV)

    stop_impersonate_account(w3, GOV)
    print("Setup completed.")


if __name__ == "__main__":
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    setup(w3)
