"""
Unit tests for bulk eth_getProof generation (grouped storage keys).

The bulk generator must:
1. Request exactly the storage keys the per-request generators request
2. Produce byte-identical RLP blobs while issuing fewer RPC calls
3. Split failing chunks and isolate failures to single requests
4. Reject responses whose storage proofs do not match the requested keys
"""

from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
import rlp
from hexbytes import HexBytes
from web3 import Web3

from votemarket_toolkit.proofs.generators.bulk_proof import (
    ProofRequest,
    generate_proofs_bulk,
    get_gauge_proof_slots,
    get_user_proof_slots,
)
from votemarket_toolkit.proofs.generators.gauge_proof import (
    generate_gauge_proof,
)
from votemarket_toolkit.proofs.generators.user_proof import (
    generate_user_proof,
)
from votemarket_toolkit.proofs.manager import VoteMarketProofs

CONTROLLER = "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB"
GAUGES = [
    "0xd5f2e6612e41be48461fdba20061e3c778fe6ec4",
    "0x7E1444BA99dcdFfE8fBdb42C02fb0DA4AAAcE4d5",
]
USERS = [
    "0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6",
    "0x989AEb4d175e16225E39E87d0D97A3360524AD80",
    "0xF147b8125d2ef93FB6965Db97D6746952a133934",
]
EPOCH = 1764806400  # week-aligned
BLOCK = 21000000
PROTOCOLS = ["curve", "balancer", "frax", "fxn", "pendle", "yb"]

ACCOUNT_PROOF = [rlp.encode([b"account-node", bytes([i])]) for i in range(3)]


def _key_int(key: Any) -> int:
    if isinstance(key, str):
        return int(key, 16)
    return int.from_bytes(bytes(HexBytes(key)), "big")


def _fake_storage_proof(key: Any) -> Dict[str, Any]:
    """Deterministic, valid-RLP proof nodes derived from the key."""
    key_bytes = _key_int(key).to_bytes(32, "big")
    nodes = [rlp.encode([key_bytes, b"node", bytes([i])]) for i in range(3)]
    return {"key": HexBytes(key_bytes), "value": 0, "proof": nodes}


class FakeEth:
    """Records eth_getProof calls and synthesizes deterministic proofs."""

    def __init__(self, behaviour: Optional[Callable[[List[str]], None]]):
        self.calls: List[tuple] = []
        self.behaviour = behaviour

    def get_proof(self, address, keys, block):
        keys = list(keys)
        self.calls.append((address, keys, block))
        if self.behaviour is not None:
            self.behaviour(keys)
        return {
            "accountProof": list(ACCOUNT_PROOF),
            "storageProof": [_fake_storage_proof(k) for k in keys],
        }


class FakeWeb3:
    to_checksum_address = staticmethod(Web3.to_checksum_address)
    to_hex = staticmethod(Web3.to_hex)

    def __init__(self, behaviour: Optional[Callable] = None):
        self.eth = FakeEth(behaviour)


@pytest.fixture(autouse=True)
def _static_gauge_controller():
    """Avoid the network-backed registry: fixed controller address."""
    with patch(
        "votemarket_toolkit.shared.registry.get_gauge_controller",
        return_value=CONTROLLER,
    ):
        yield


def _requests() -> List[ProofRequest]:
    requests = [ProofRequest.for_gauge(g, EPOCH) for g in GAUGES]
    requests += [ProofRequest.for_user(GAUGES[0], u) for u in USERS]
    requests.append(ProofRequest.for_user(GAUGES[1], USERS[0]))
    return requests


def _reference_proofs(protocol: str, requests: List[ProofRequest]):
    """What the toolkit produces today: one eth_getProof per request."""
    w3 = FakeWeb3()
    expected = {}
    for request in requests:
        if request.kind == "gauge":
            expected[request] = generate_gauge_proof(
                w3, protocol, request.gauge, request.epoch, BLOCK
            )
        else:
            expected[request] = generate_user_proof(
                w3, protocol, request.gauge, request.user, BLOCK
            )
    return expected, len(w3.eth.calls)


# =============================================================================
# 1. Slot parity with the existing generators
# =============================================================================


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_bulk_slots_match_existing_generators(protocol):
    w3 = FakeWeb3()
    generate_gauge_proof(w3, protocol, GAUGES[0], EPOCH, BLOCK)
    generate_user_proof(w3, protocol, GAUGES[0], USERS[0], BLOCK)

    (addr_gauge, keys_gauge, block_gauge), (addr_user, keys_user, _) = (
        w3.eth.calls
    )

    assert keys_gauge == get_gauge_proof_slots(protocol, GAUGES[0], EPOCH)
    assert keys_user == get_user_proof_slots(protocol, GAUGES[0], USERS[0])
    assert addr_gauge == addr_user == Web3.to_checksum_address(CONTROLLER)
    assert block_gauge == BLOCK


# =============================================================================
# 2. Byte identity + fewer RPC calls
# =============================================================================


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.parametrize("keys_per_call", [1, 2, 4, 100])
def test_bulk_is_byte_identical_to_single(protocol, keys_per_call):
    requests = _requests()
    expected, single_calls = _reference_proofs(protocol, requests)

    w3 = FakeWeb3()
    result = generate_proofs_bulk(
        w3, protocol, BLOCK, requests, keys_per_call=keys_per_call
    )

    assert result.errors == {}
    assert set(result.proofs) == set(requests)
    for request in requests:
        assert result.proofs[request] == expected[request]

    assert result.stats.requests == len(requests)
    assert result.stats.rpc_calls == len(w3.eth.calls)
    assert len(w3.eth.calls) <= single_calls
    if keys_per_call == 100:
        assert len(w3.eth.calls) == 1
    largest_request = max(
        len(get_user_proof_slots(protocol, g, u))
        for g in GAUGES
        for u in USERS
    )
    for _, keys, block in w3.eth.calls:
        assert len(keys) <= max(keys_per_call, largest_request)
        assert block == BLOCK


def test_bulk_uses_gauge_controller_address():
    w3 = FakeWeb3()
    generate_proofs_bulk(w3, "curve", BLOCK, _requests())
    assert {addr for addr, _, _ in w3.eth.calls} == {
        Web3.to_checksum_address(CONTROLLER)
    }


def test_requests_are_deduplicated_and_normalized():
    first = ProofRequest.for_user(GAUGES[0].lower(), USERS[0].upper())
    second = ProofRequest.for_user(GAUGES[0].upper(), USERS[0].lower())
    assert first == second

    w3 = FakeWeb3()
    result = generate_proofs_bulk(w3, "curve", BLOCK, [first, second])

    assert result.stats.requests == 1
    assert len(w3.eth.calls) == 1
    assert len(w3.eth.calls[0][1]) == 3  # last_vote, slope, end
    assert set(result.proofs) == {first}


def test_empty_requests_make_no_rpc_call():
    w3 = FakeWeb3()
    result = generate_proofs_bulk(w3, "curve", BLOCK, [])
    assert result.proofs == {} and result.errors == {}
    assert w3.eth.calls == []


# =============================================================================
# 3. Failure handling: split, isolate
# =============================================================================


def test_oversized_chunks_are_split_and_recovered():
    def reject_big(keys):
        if len(keys) > 4:
            raise ValueError("response too large")

    requests = _requests()
    expected, _ = _reference_proofs("curve", requests)

    w3 = FakeWeb3(reject_big)
    result = generate_proofs_bulk(
        w3, "curve", BLOCK, requests, keys_per_call=100
    )

    assert result.errors == {}
    assert result.stats.splits >= 1
    assert all(result.proofs[r] == expected[r] for r in requests)
    assert result.stats.rpc_calls == len(w3.eth.calls)


def test_failing_request_is_isolated():
    poison = get_user_proof_slots("curve", GAUGES[0], USERS[1])[0]

    def poison_key(keys):
        if poison in keys:
            raise ConnectionError("boom")

    requests = _requests()
    expected, _ = _reference_proofs("curve", requests)
    bad = ProofRequest.for_user(GAUGES[0], USERS[1])

    w3 = FakeWeb3(poison_key)
    result = generate_proofs_bulk(
        w3, "curve", BLOCK, requests, keys_per_call=100, max_retries=1
    )

    assert set(result.errors) == {bad}
    assert isinstance(result.errors[bad], ConnectionError)
    assert set(result.proofs) == set(requests) - {bad}
    assert all(result.proofs[r] == expected[r] for r in result.proofs)
    assert result.stats.failed_requests == 1


def test_misordered_storage_proofs_are_rejected():
    class ReversingEth(FakeEth):
        def get_proof(self, address, keys, block):
            response = super().get_proof(address, keys, block)
            response["storageProof"].reverse()
            return response

    w3 = FakeWeb3()
    w3.eth = ReversingEth(None)
    requests = [ProofRequest.for_user(GAUGES[0], USERS[0])]

    result = generate_proofs_bulk(w3, "curve", BLOCK, requests, max_retries=1)

    assert result.proofs == {}
    assert set(result.errors) == set(requests)
    assert "order mismatch" in str(result.errors[requests[0]])


def test_wrong_number_of_storage_proofs_is_rejected():
    class DroppingEth(FakeEth):
        def get_proof(self, address, keys, block):
            response = super().get_proof(address, keys, block)
            response["storageProof"].pop()
            return response

    w3 = FakeWeb3()
    w3.eth = DroppingEth(None)
    requests = [ProofRequest.for_user(GAUGES[0], USERS[0])]

    result = generate_proofs_bulk(w3, "curve", BLOCK, requests, max_retries=1)

    assert result.proofs == {}
    assert set(result.errors) == set(requests)


def test_invalid_configuration_raises():
    w3 = FakeWeb3()
    with pytest.raises(ValueError):
        generate_proofs_bulk(w3, "curve", BLOCK, _requests(), keys_per_call=0)
    with pytest.raises(ValueError):
        generate_proofs_bulk(w3, "unknown-protocol", BLOCK, _requests())
    with pytest.raises(ValueError):
        ProofRequest(kind="gauge", gauge=GAUGES[0])  # missing epoch
    with pytest.raises(ValueError):
        ProofRequest(kind="user", gauge=GAUGES[0])  # missing user


# =============================================================================
# 4. VoteMarketProofs.get_proofs_bulk
# =============================================================================


@pytest.fixture
def proof_manager():
    with patch(
        "votemarket_toolkit.proofs.manager.GlobalConstants.get_rpc_url"
    ) as mock_rpc:
        mock_rpc.return_value = "http://localhost:8545"
        with patch(
            "votemarket_toolkit.proofs.manager.Web3Service"
        ) as mock_ws_class:
            mock_ws = MagicMock()
            mock_ws_class.return_value = mock_ws
            manager = VoteMarketProofs(chain_id=1)
            manager.web3_service = mock_ws
            return manager


def test_manager_bulk_matches_per_request_methods(proof_manager):
    proof_manager.web3_service.w3 = FakeWeb3()

    result = proof_manager.get_proofs_bulk(
        "curve",
        BLOCK,
        gauge_epochs=[(GAUGES[0], EPOCH + 3600)],  # not week-aligned
        users=[(GAUGES[0], USERS[0]), (GAUGES[1], USERS[1])],
    )

    assert result.success and not result.errors and not result.is_partial
    data = result.data

    gauge_ref = proof_manager.get_gauge_proof(
        "curve", GAUGES[0], EPOCH + 3600, BLOCK
    ).unwrap()
    assert data.gauge_proofs[(GAUGES[0].lower(), EPOCH)] == gauge_ref

    for gauge, user in [(GAUGES[0], USERS[0]), (GAUGES[1], USERS[1])]:
        user_ref = proof_manager.get_user_proof(
            "curve", gauge, user, BLOCK
        ).unwrap()
        assert data.user_proofs[(gauge.lower(), user.lower())] == user_ref

    assert data.stats.requests == 3
    assert data.stats.rpc_calls == 1


def test_manager_bulk_partial_success(proof_manager):
    poison = get_user_proof_slots("curve", GAUGES[0], USERS[1])[0]

    def poison_key(keys):
        if poison in keys:
            raise ConnectionError("boom")

    proof_manager.web3_service.w3 = FakeWeb3(poison_key)

    result = proof_manager.get_proofs_bulk(
        "curve",
        BLOCK,
        gauge_epochs=[(GAUGES[0], EPOCH)],
        users=[(GAUGES[0], u) for u in USERS],
        max_retries=1,
    )

    assert result.success and result.is_partial
    assert len(result.errors) == 1
    assert result.errors[0].source == "user_proof"
    assert result.errors[0].context["user"] == USERS[1].lower()
    assert (GAUGES[0].lower(), USERS[1].lower()) not in result.data.user_proofs
    assert len(result.data.user_proofs) == 2
    assert (GAUGES[0].lower(), EPOCH) in result.data.gauge_proofs


def test_manager_bulk_total_failure(proof_manager):
    def always_fail(keys):
        raise ConnectionError("rpc down")

    proof_manager.web3_service.w3 = FakeWeb3(always_fail)

    result = proof_manager.get_proofs_bulk(
        "curve",
        BLOCK,
        gauge_epochs=[(GAUGES[0], EPOCH)],
        users=[(GAUGES[0], USERS[0])],
        max_retries=1,
    )

    assert not result.success
    assert result.data is None
    assert {e.source for e in result.errors} == {"gauge_proof", "user_proof"}


def test_manager_bulk_configuration_error_is_failure(proof_manager):
    proof_manager.web3_service.w3 = FakeWeb3()
    result = proof_manager.get_proofs_bulk(
        "unknown-protocol", BLOCK, users=[(GAUGES[0], USERS[0])]
    )
    assert not result.success
    assert result.errors[0].source == "bulk_proof"


def test_invalid_request_is_isolated_not_fatal():
    """A malformed address fails that request only, not the whole batch."""
    valid = _requests()
    bad = ProofRequest.for_user(GAUGES[0], "0xnot-an-address")
    expected, _ = _reference_proofs("curve", valid)

    w3 = FakeWeb3()
    result = generate_proofs_bulk(w3, "curve", BLOCK, valid + [bad])

    assert bad in result.errors
    assert set(result.proofs) == set(valid)
    assert all(result.proofs[r] == expected[r] for r in valid)
    assert result.stats.failed_requests == 1


def test_missing_response_key_is_rejected():
    """A storage proof entry without a 'key' field must not be trusted."""

    class KeylessEth(FakeEth):
        def get_proof(self, address, keys, block):
            response = super().get_proof(address, keys, block)
            for entry in response["storageProof"]:
                del entry["key"]
            return response

    w3 = FakeWeb3()
    w3.eth = KeylessEth(None)
    requests = [ProofRequest.for_user(GAUGES[0], USERS[0])]

    result = generate_proofs_bulk(w3, "curve", BLOCK, requests, max_retries=1)

    assert result.proofs == {}
    assert set(result.errors) == set(requests)


def test_transport_error_retries_chunk_before_splitting():
    """A transient transport error retries the same chunk, no split storm."""
    state = {"calls": 0}

    def flaky(keys):
        state["calls"] += 1
        if state["calls"] == 1:
            raise ConnectionError("transient blip")

    requests = _requests()
    expected, _ = _reference_proofs("curve", requests)

    w3 = FakeWeb3(flaky)
    result = generate_proofs_bulk(
        w3, "curve", BLOCK, requests, keys_per_call=100
    )

    assert result.errors == {}
    assert result.stats.splits == 0
    assert len(w3.eth.calls) == 2  # first attempt + one chunk retry
    assert all(result.proofs[r] == expected[r] for r in requests)


def test_provider_outage_triggers_circuit_breaker():
    """A persistent outage aborts instead of storming the provider."""

    def always_fail(keys):
        raise ConnectionError("rpc down")

    requests = [
        ProofRequest.for_user(GAUGES[0], f"0x{i:040x}") for i in range(1, 30)
    ]
    w3 = FakeWeb3(always_fail)

    result = generate_proofs_bulk(
        w3,
        "curve",
        BLOCK,
        requests,
        keys_per_call=100,
        max_retries=1,
        abort_after_failures=3,
    )

    assert result.stats.aborted
    assert result.proofs == {}
    assert set(result.errors) == set(requests)
    assert len(w3.eth.calls) < len(requests)


def test_manager_bulk_malformed_input_returns_failure(proof_manager):
    """Bad tuple shapes are wrapped in Result.fail, never raised."""
    proof_manager.web3_service.w3 = FakeWeb3()

    result = proof_manager.get_proofs_bulk(
        "curve", BLOCK, users=[("0xdeadbeef",)]
    )

    assert not result.success
    assert result.errors[0].source == "bulk_proof"
