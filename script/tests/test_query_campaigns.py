from typing import List
from ape import networks
from votes.query_campaigns import query_active_campaigns
from shared.types import Campaign

def test_query_active_campaigns(setup_environment, web3_service):
    votemarket = setup_environment["votemarket"]
    campaign1_id = setup_environment["campaign1_id"]
    campaign2_id = setup_environment["campaign2_id"]

    print(f"Campaign count: {votemarket.campaignCount()}")

    # Query active campaigns
    active_campaigns = query_active_campaigns(web3_service, 42161, votemarket.address)
    print(f"Active campaigns: {active_campaigns}")

    # Assert that we have exactly two active campaigns
    assert (
        len(active_campaigns) == 2
    ), f"Expected 2 active campaigns, but got {len(active_campaigns)}"

    # Define expected values
    expected_campaigns: List[Campaign] = [
        {
            "id": campaign1_id,
            "chain_id": 42161,
            "gauge": "0xf1bb643f953836725c6e48bdd6f1816f871d3e07",
            "blacklist": [
                "0xDEAD000000000000000000000000000000000000",
                "0x0100000000000000000000000000000000000000",
            ],
        },
        {
            "id": campaign2_id,
            "chain_id": 42161,
            "gauge": "0x059e0db6bf882f5fe680dc5409c7adeb99753736",
            "blacklist": [
                "0xDEAD000000000000000000000000000000000000",
                "0x0100000000000000000000000000000000000000",
            ],
        },
    ]

    # Verify that the returned campaigns match the expected values
    for expected, actual in zip(expected_campaigns, active_campaigns):
        assert actual["id"] == expected["id"], f"Campaign ID mismatch for campaign {expected['id']}"
        assert not votemarket.isClosedCampaign(actual["id"]), f"Campaign {actual['id']} should not be closed"

        # Check campaign details
        assert actual["chain_id"] == expected["chain_id"], f"Incorrect chain ID for campaign {actual['id']}"
        assert actual["gauge"].lower() == expected["gauge"].lower(), f"Incorrect gauge for campaign {actual['id']}"

        # Check blacklist
        assert isinstance(actual["blacklist"], list), f"Blacklist for campaign {actual['id']} should be a list"
        assert len(actual["blacklist"]) == len(expected["blacklist"]), f"Incorrect number of blacklisted addresses for campaign {actual['id']}"
        for addr in expected["blacklist"]:
            assert addr.lower() in [a.lower() for a in actual["blacklist"]], f"Address {addr} not found in campaign {actual['id']} blacklist"
