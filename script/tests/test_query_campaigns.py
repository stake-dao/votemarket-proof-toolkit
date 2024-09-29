import pytest
from ape import accounts, project, Contract
from shared.utils import load_json
from votes.query_campaigns import query_active_campaigns
from shared.web3_service import initialize_web3_service, get_web3_service

ARB_TOKEN_ADDRESS = "0x912CE59144191C1204E64559FE8253a0e49E6548"
WHALE_ADDRESS = "0xF977814e90dA44bFA03b6295A0616a897441aceC"


@pytest.fixture(scope="session")
def arb_token():
    return Contract(ARB_TOKEN_ADDRESS)


@pytest.fixture(scope="session")
def votemarket():
    return Contract(
        "0x6c8fc8482fae6fe8cbe66281a4640aa19c4d9c8e",
        abi=load_json("abi/vm_platform.json"),
    )


@pytest.fixture(scope="session")
def whale(accounts):
    return accounts[WHALE_ADDRESS]


@pytest.fixture(scope="session", autouse=True)
def initialize_web3():
    initialize_web3_service(
        42161, "http://localhost:8545"
    )


@pytest.fixture(scope="session")
def setup_environment(votemarket, arb_token, whale):
    # Impersonate the whale
    with accounts.use_sender(whale):
        # Fund accounts
        user1 = accounts.test_accounts[1]
        user2 = accounts.test_accounts[2]

        user1.balance = "10 ether"
        user2.balance = "10 ether"

        # Approve ARB tokens for VoteMarket
        arb_amount = 1_000_000 * 10**18  # 1 million ARB tokens
        arb_token.approve(votemarket.address, arb_amount, sender=whale)

        # Create a test campaign
        assert votemarket.campaignCount() == 0

        # Create a test campaign
        votemarket.createCampaign(
            42161,  # chainId (Arbitrum)
            "0x1234567890123456789012345678901234567890",  # gauge
            whale.address,  # manager
            arb_token.address,  # rewardToken
            4,  # numberOfPeriods
            1000 * 10**18,  # maxRewardPerVote
            100_000 * 10**18,  # totalRewardAmount
            [],  # addresses
            "0x0000000000000000000000000000000000000000",  # hook
            False,  # isWhitelist
            sender=whale,
        )

        assert votemarket.campaignCount() == 1

        return {
            "votemarket": votemarket,
            "arb_token": arb_token,
            "whale": whale,
            "user1": user1,
            "user2": user2,
        }


def test_query_active_campaigns(setup_environment):
    votemarket = setup_environment["votemarket"]

    print(votemarket.campaignCount())

    # Initialize web3 service
    initialize_web3_service(42161, "http://localhost:8545")

    # Query active campaigns
    active_campaigns = query_active_campaigns(42161, votemarket.address)

    # Assert that we have at least one active campaign
    assert len(active_campaigns) > 0

    # Verify that the returned addresses are valid
    for campaign in active_campaigns:
        assert votemarket.isClosedCampaign(campaign) == False


def test_arb_approval(setup_environment):
    votemarket = setup_environment["votemarket"]
    arb_token = setup_environment["arb_token"]
    whale = setup_environment["whale"]

    # Check if the approval was successful
    allowance = arb_token.allowance(whale.address, votemarket.address)
    print(allowance)
    # assert allowance >= 1_000_000 * 10**18, "ARB token approval failed"
