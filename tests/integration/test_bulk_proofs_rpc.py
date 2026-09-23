"""
Integration test: bulk eth_getProof == per-request eth_getProof on a live RPC.

Requires ETHEREUM_MAINNET_RPC_URL (archive not needed: uses a recent block).
"""

import os
import time

import pytest
from web3 import Web3

from votemarket_toolkit.proofs.generators.bulk_proof import (
    ProofRequest,
    generate_proofs_bulk,
)
from votemarket_toolkit.proofs.generators.gauge_proof import (
    generate_gauge_proof,
)
from votemarket_toolkit.proofs.generators.user_proof import (
    generate_user_proof,
)
from votemarket_toolkit.utils import get_rounded_epoch

RPC_URL = os.getenv("ETHEREUM_MAINNET_RPC_URL")

GAUGES = [
    "0xd5f2e6612e41be48461fdba20061e3c778fe6ec4",
    "0x7E1444BA99dcdFfE8fBdb42C02fb0DA4AAAcE4d5",
]
USERS = [
    "0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6",
    "0x989AEb4d175e16225E39E87d0D97A3360524AD80",
]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not RPC_URL, reason="ETHEREUM_MAINNET_RPC_URL not set"),
]


def test_bulk_matches_per_request_on_live_rpc():
    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 60}))
    block = w3.eth.block_number - 5
    epoch = get_rounded_epoch(int(time.time()))

    requests = [ProofRequest.for_gauge(g, epoch) for g in GAUGES]
    requests += [ProofRequest.for_user(GAUGES[0], u) for u in USERS]

    bulk = generate_proofs_bulk(
        w3, "curve", block, requests, keys_per_call=100
    )
    assert bulk.errors == {}
    assert bulk.stats.rpc_calls == 1

    for request in requests:
        if request.kind == "gauge":
            reference = generate_gauge_proof(
                w3, "curve", request.gauge, request.epoch, block
            )
        else:
            reference = generate_user_proof(
                w3, "curve", request.gauge, request.user, block
            )
        assert bulk.proofs[request] == reference
