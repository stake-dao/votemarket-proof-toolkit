import pytest
from ape import Contract
from eth_utils import to_checksum_address
from shared.utils import load_json
from votes.query_campaigns import query_active_campaigns
from shared.web3_service import initialize_web3_service

ARB_TOKEN_ADDRESS = to_checksum_address(
    "0x912CE59144191C1204E64559FE8253a0e49E6548".lower()
)
WHALE_ADDRESS = to_checksum_address(
    "0xF977814e90dA44bFA03b6295A0616a897441aceC".lower()
)


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
def verifier():
    return Contract(
        "0x348d1bd2a18c9a93eb9ab8e5f55852da3036e225",
        abi=load_json("abi/verifier.json"),
    )


@pytest.fixture(scope="session")
def whale(accounts):
    return accounts[WHALE_ADDRESS]


@pytest.fixture(scope="session", autouse=True)
def initialize_web3():
    initialize_web3_service(42161, "http://localhost:8545")


def test_query_active_campaigns(setup_environment):
    votemarket = setup_environment["votemarket"]
    whale = setup_environment["whale"]
    campaign1_id = setup_environment["campaign1_id"]
    campaign2_id = setup_environment["campaign2_id"]

    print(f"Campaign count: {votemarket.campaignCount()}")

    # Query active campaigns
    active_campaigns = query_active_campaigns(42161, votemarket.address)
    print(f"Active campaigns: {active_campaigns}")

    # Assert that we have exactly two active campaigns
    assert (
        len(active_campaigns) == 2
    ), f"Expected 2 active campaigns, but got {len(active_campaigns)}"

    # Define expected values
    expected_campaigns = [
        {
            "id": campaign1_id,
            "gauge": "0xf1bb643f953836725c6e48bdd6f1816f871d3e07",
            "manager": whale.address,
            "rewardToken": setup_environment["arb_token"].address,
            "numberOfPeriods": 4,
            "maxRewardPerVote": 1000 * 10**18,
            "totalRewardAmount": 100_000 * 10**18,
        },
        {
            "id": campaign2_id,
            "gauge": "0x059e0db6bf882f5fe680dc5409c7adeb99753736",
            "manager": whale.address,
            "rewardToken": setup_environment["arb_token"].address,
            "numberOfPeriods": 4,
            "maxRewardPerVote": 1000 * 10**18,
            "totalRewardAmount": 100_000 * 10**18,
        },
    ]

    # Verify that the returned campaigns match the expected values
    for expected, actual in zip(expected_campaigns, active_campaigns):
        assert (
            actual["id"] == expected["id"]
        ), f"Campaign ID mismatch for campaign {expected['id']}"
        assert not votemarket.isClosedCampaign(
            actual["id"]
        ), f"Campaign {actual['id']} should not be closed"

        # Check campaign details
        assert (
            actual["campaign"]["chainId"] == 42161
        ), f"Incorrect chain ID for campaign {actual['id']}"
        assert (
            actual["campaign"]["gauge"].lower() == expected["gauge"].lower()
        ), f"Incorrect gauge for campaign {actual['id']}"
        assert (
            actual["campaign"]["manager"].lower() == expected["manager"].lower()
        ), f"Incorrect manager for campaign {actual['id']}"
        assert (
            actual["campaign"]["rewardToken"].lower() == expected["rewardToken"].lower()
        ), f"Incorrect reward token for campaign {actual['id']}"
        assert (
            actual["campaign"]["numberOfPeriods"] == expected["numberOfPeriods"]
        ), f"Incorrect number of periods for campaign {actual['id']}"
        assert (
            actual["campaign"]["maxRewardPerVote"] == expected["maxRewardPerVote"]
        ), f"Incorrect max reward per vote for campaign {actual['id']}"
        assert (
            actual["campaign"]["totalRewardAmount"] == expected["totalRewardAmount"]
        ), f"Incorrect total reward amount for campaign {actual['id']}"

        # Check additional fields
        assert (
            actual["isClosed"] == False
        ), f"Campaign {actual['id']} should not be closed"
        assert (
            actual["isWhitelistOnly"] == False
        ), f"Campaign {actual['id']} should not be whitelist only"
        assert isinstance(
            actual["addresses"], tuple
        ), f"Addresses for campaign {actual['id']} should be a tuple"
        assert isinstance(
            actual["currentPeriod"], dict
        ), f"Current period for campaign {actual['id']} should be a dict"
        assert isinstance(
            actual["periodLeft"], int
        ), f"Period left for campaign {actual['id']} should be an integer"
