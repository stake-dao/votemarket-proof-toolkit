import os
import pytest
from ape import accounts, Contract
from shared.utils import load_json
from shared.web3_service import Web3Service
from proofs.main import VoteMarketProofs
from votes.main import VMVotes
from eth_utils import to_checksum_address

ARB_TOKEN_ADDRESS = to_checksum_address(
    "0x912CE59144191C1204E64559FE8253a0e49E6548".lower()
)
WHALE_ADDRESS = to_checksum_address(
    "0xF977814e90dA44bFA03b6295A0616a897441aceC".lower()
)
VOTEMARKET_ADDRESS = to_checksum_address(
    "0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e".lower()
)
VERIFIER_ADDRESS = to_checksum_address(
    "0x348d1bd2a18c9a93eb9ab8e5f55852da3036e225".lower()
)
ORACLE_ADDRESS = to_checksum_address(
    "0xa20b142c2d52193e9de618dc694eba673410693f".lower()
)
GOVERNANCE_ADDRESS = to_checksum_address(
    "0xE9847f18710ebC1c46b049e594c658B9412cba6e".lower()
)


@pytest.fixture(scope="session", autouse=True)
def web3_service():
    return Web3Service(42161, "http://localhost:8545")


@pytest.fixture(scope="session")
def vm_proofs():
    return VoteMarketProofs(
        1, "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
    )


@pytest.fixture(scope="session")
def vm_votes():
    return VMVotes(
        1, "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
    )


@pytest.fixture(scope="session")
def arb_token():
    return Contract(ARB_TOKEN_ADDRESS, abi=load_json("abi/erc20.json"))


@pytest.fixture(scope="session")
def votemarket():
    return Contract(
        VOTEMARKET_ADDRESS,
        abi=load_json("abi/vm_platform.json"),
    )


@pytest.fixture(scope="session")
def verifier():
    return Contract(
        VERIFIER_ADDRESS,
        abi=load_json("abi/verifier.json"),
    )


@pytest.fixture(scope="session")
def oracle():
    return Contract(
        ORACLE_ADDRESS,
        abi=load_json("abi/oracle.json"),
    )


@pytest.fixture(scope="session")
def whale(accounts):
    return accounts[WHALE_ADDRESS]


@pytest.fixture(scope="session")
def governance(accounts):
    return accounts[GOVERNANCE_ADDRESS]


@pytest.fixture(scope="session")
def create_campaign(votemarket, whale, arb_token):
    def _create_campaign(
        gauge: str = "0x1234567890123456789012345678901234567890",
        manager: str = None,
        reward_token: str = None,
        number_of_periods: int = 4,
        max_reward_per_vote: int = 1000 * 10**18,
        total_reward_amount: int = 100_000 * 10**18,
        addresses: list = ["0xDEAD000000000000000000000000000000000000", "0x0100000000000000000000000000000000000000"],
        hook: str = "0x0000000000000000000000000000000000000000",
        is_whitelist: bool = False,
    ):
        manager = manager or whale.address
        reward_token = reward_token or arb_token.address

        with accounts.use_sender(whale):
            votemarket.createCampaign(
                42161,  # chainId (Arbitrum)
                gauge,
                manager,
                reward_token,
                number_of_periods,
                max_reward_per_vote,
                total_reward_amount,
                addresses,
                hook,
                is_whitelist,
                sender=whale,
            )
        return votemarket.campaignCount() - 1

    return _create_campaign


@pytest.fixture(scope="session")
def setup_environment(votemarket, arb_token, whale, create_campaign, oracle, verifier):
    with accounts.use_sender(whale):
        # Fund accounts
        whale = accounts[WHALE_ADDRESS]
        governance = accounts[GOVERNANCE_ADDRESS]
        whale.balance = "10 ether"
        governance.balance = "10 ether"

        # Approve ARB tokens for VoteMarket
        arb_amount = 1_000_000 * 10**18  # 1 million ARB tokens
        arb_token.approve(votemarket.address, arb_amount, sender=whale)

        # Create two test campaigns with different gauges
        campaign1_id = create_campaign(
            gauge="0xf1bb643f953836725c6e48bdd6f1816f871d3e07"
        )
        campaign2_id = create_campaign(
            gauge="0x059e0db6bf882f5fe680dc5409c7adeb99753736"
        )

        # Authorize whale + verifier as block provider
        with accounts.use_sender(governance):
            oracle.setAuthorizedBlockNumberProvider(whale.address)
            oracle.setAuthorizedBlockNumberProvider(verifier.address)
            oracle.setAuthorizedDataProvider(verifier.address)

        assert votemarket.campaignCount() == 2

        return {
            "votemarket": votemarket,
            "arb_token": arb_token,
            "whale": whale,
            "governance": governance,
            "campaign1_id": campaign1_id,
            "campaign2_id": campaign2_id,
            "oracle": oracle,
            "verifier": verifier,
        }
