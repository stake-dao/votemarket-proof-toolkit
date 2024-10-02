""" All constants for the project """

import os
from dotenv import load_dotenv

load_dotenv()


class GaugeControllerConstants:
    """Global class constants Gauge Controller related ops"""

    VOTE_EVENT_HASH = (
        "0x45ca9a4c8d0119eb329e580d28fe689e484e1be230da8037ade9547d2d25cc91"
    )

    GAUGES_SLOTS = {
        "curve": {
            "point_weights": 12,
            "last_user_vote": 11,
            "vote_user_slope": 9,
        },
        "balancer": {
            "point_weights": 1000000008,
            "last_user_vote": 1000000007,
            "vote_user_slope": 1000000005,
        },
        "frax": {
            "point_weights": 10000000011,
            "last_user_vote": 1000000010,
            "vote_user_slope": 1000000008,
        },
        "fxn": {
            "point_weights": 10000000011,
            "last_user_vote": 1000000010,
            "vote_user_slope": 1000000008,
        },
    }

    GAUGE_CONTROLLER = {
        "curve": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
        "balancer": "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD",
        "frax": "0x3669C421b77340B2979d1A00a792CC2ee0FcE737",
        "fxn": "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37",
    }

    CREATION_BLOCKS = {
        "curve": 10647875,
        "balancer": 14457014,
        "frax": 14052749,
        "fxn": 18156185,
    }


class GaugeVotesConstants:
    """Global class constants Gauge Votes related ops"""

    GAUGE_CONTROLLER = {
        "curve": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
        "balancer": "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD",
        "frax": "0x3669C421b77340B2979d1A00a792CC2ee0FcE737",
        "fxn": "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37",
    }


class GlobalConstants:
    """Global class constants for the project"""

    REGISTRY = "0x4d26cb6658aedce7aeff79bd14121ef48b911253"

    CHAIN_ID_TO_RPC = {
        1: os.getenv("ETHEREUM_MAINNET_RPC_URL"),
        56: os.getenv("BSC_MAINNET_RPC_URL"),
        42161: os.getenv("ARBITRUM_MAINNET_RPC_URL"),
    }
