import os
import pytest
import ape
from ape import accounts, project, Contract
from shared.utils import load_json
from shared.web3_service import initialize_web3_service
from proofs.VMProofs import VoteMarketProofs
from votes.VMVotes import VMVotes

ARB_TOKEN_ADDRESS = "0x912CE59144191C1204E64559FE8253a0e49E6548"
WHALE_ADDRESS = "0xF977814e90dA44bFA03b6295A0616a897441aceC"
VOTEMARKET_ADDRESS = "0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e"
VERIFIER_ADDRESS = "0x348d1bd2a18c9a93eb9ab8e5f55852da3036e225"
ORACLE_ADDRESS = "0xa20b142c2d52193e9de618dc694eba673410693f"
GOVERNANCE_ADDRESS = "0xE9847f18710ebC1c46b049e594c658B9412cba6e"
MOCK_VERIFIER_ADDRESS = "0x763ff43C80896cfE639F1baEf69B921D0479eb30"

@pytest.fixture(scope="session", autouse=True)
def initialize_web3():
    initialize_web3_service(42161, "http://localhost:8545")


@pytest.fixture(scope="session")
def vm_proofs():
    return VoteMarketProofs(
        "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
    )


@pytest.fixture(scope="session")
def vm_votes():
    return VMVotes(
        "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("WEB3_ALCHEMY_API_KEY")
    )


@pytest.fixture(scope="session")
def arb_token():
    return Contract(ARB_TOKEN_ADDRESS)


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
def curve_mock_verifier():
    return Contract(
        MOCK_VERIFIER_ADDRESS,
        abi=load_json("abi/mock_verifier.json"),
    )


@pytest.fixture(scope="session")
def create_campaign(votemarket, whale, arb_token):
    def _create_campaign(
        gauge: str = "0x1234567890123456789012345678901234567890",
        manager: str = None,
        reward_token: str = None,
        number_of_periods: int = 4,
        max_reward_per_vote: int = 1000 * 10**18,
        total_reward_amount: int = 100_000 * 10**18,
        addresses: list = [],
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
def setup_environment(
    votemarket, arb_token, whale, create_campaign, oracle, curve_mock_verifier
):
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

        assert votemarket.campaignCount() == 2

        return {
            "votemarket": votemarket,
            "arb_token": arb_token,
            "whale": whale,
            "governance": governance,
            "campaign1_id": campaign1_id,
            "campaign2_id": campaign2_id,
            "curve_mock_verifier": curve_mock_verifier,
        }
