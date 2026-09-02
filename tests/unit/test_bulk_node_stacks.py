"""
Unit tests for the raw node stacks and storage root kept by the bulk generator.

The batch verifier's node bags are built from the same ``eth_getProof``
responses as the legacy blobs, so the bulk generator must:
1. Keep the raw storage-trie nodes of every requested key, in key order
2. Pin the controller ``storageHash`` and fail closed when calls disagree
3. Expose both through ``VoteMarketProofs.get_proofs_bulk``
"""

from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import pytest
import rlp
from hexbytes import HexBytes

from votemarket_toolkit.proofs.generators.bulk_proof import (
    ProofRequest,
    generate_proofs_bulk,
    get_user_proof_slots,
)
from votemarket_toolkit.proofs.generators.node_bag import encode_node_bag
from votemarket_toolkit.proofs.manager import VoteMarketProofs

CONTROLLER = "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB"
GAUGE = "0xd5f2e6612e41be48461fdba20061e3c778fe6ec4"
USERS = [
    "0x52f541764E6e90eeBc5c21Ff570De0e2D63766B6",
    "0x989AEb4d175e16225E39E87d0D97A3360524AD80",
    "0xF147b8125d2ef93FB6965Db97D6746952a133934",
    "0x7a16fF8270133F063aAb6C9977183D9e72835428",
]
EPOCH = 1764806400
BLOCK = 21000000
STORAGE_ROOT = HexBytes(b"\x42" * 32)
OTHER_ROOT = HexBytes(b"\x24" * 32)
ACCOUNT_PROOF = [rlp.encode([b"account-node", bytes([i])]) for i in range(3)]


def _key_int(key: Any) -> int:
    if isinstance(key, str):
        return int(key, 16)
    return int.from_bytes(bytes(HexBytes(key)), "big")


def _fake_nodes(key: Any) -> List[bytes]:
    """Deterministic nodes: a shared root, a per-key branch, a per-key leaf."""
    key_bytes = _key_int(key).to_bytes(32, "big")
    return [
        rlp.encode([b"shared-root", b"\x00" * 40]),
        rlp.encode([key_bytes, b"branch"]),
        rlp.encode([key_bytes, b"leaf", b"value"]),
    ]


class FakeEth:
    def __init__(self, roots: Optional[List[HexBytes]] = None):
        self.calls = 0
        self.roots = roots or []

    def get_proof(self, address, keys, block):
        keys = list(keys)
        root = (
            self.roots[self.calls]
            if self.calls < len(self.roots)
            else STORAGE_ROOT
        )
        self.calls += 1
        return {
            "accountProof": list(ACCOUNT_PROOF),
            "storageHash": root,
            "storageProof": [
                {
                    "key": HexBytes(_key_int(k).to_bytes(32, "big")),
                    "value": 0,
                    "proof": ["0x" + n.hex() for n in _fake_nodes(k)],
                }
                for k in keys
            ],
        }


class FakeWeb3:
    def __init__(self, roots: Optional[List[HexBytes]] = None):
        self.eth = FakeEth(roots)


@pytest.fixture(autouse=True)
def _static_gauge_controller():
    with patch(
        "votemarket_toolkit.shared.registry.get_gauge_controller",
        return_value=CONTROLLER,
    ):
        yield


def _user_requests() -> List[ProofRequest]:
    return [ProofRequest.for_user(GAUGE, user) for user in USERS]


def test_node_stacks_are_kept_per_request_in_key_order():
    result = generate_proofs_bulk(FakeWeb3(), "curve", BLOCK, _user_requests())

    assert not result.errors
    assert result.storage_root == bytes(STORAGE_ROOT)
    for request in _user_requests():
        slots = get_user_proof_slots("curve", GAUGE, request.user)
        stacks = result.node_stacks[request]
        assert len(stacks) == len(slots) == 3
        for slot, stack in zip(slots, stacks):
            assert stack == _fake_nodes(slot)
            assert all(isinstance(node, bytes) for node in stack)


def test_stacks_survive_chunk_splitting():
    web3 = FakeWeb3()
    result = generate_proofs_bulk(
        web3, "curve", BLOCK, _user_requests(), keys_per_call=3
    )
    assert web3.eth.calls == len(USERS)
    assert len(result.node_stacks) == len(USERS)
    assert result.storage_root == bytes(STORAGE_ROOT)


def test_storage_root_mismatch_splits_then_fails_closed():
    # 4 users x 3 keys, 6 keys per call: chunks [u0,u1] and [u2,u3]. The
    # second call reports another storageHash: the chunk is split (marker
    # error, no chunk-level retry), each singleton retries the whole call
    # `max_retries` times, disagrees again and ends in `errors`. The first
    # chunk's proofs and the pinned root are kept.
    roots = [STORAGE_ROOT] + [OTHER_ROOT] * 20
    web3 = FakeWeb3(roots)
    result = generate_proofs_bulk(
        web3,
        "curve",
        BLOCK,
        _user_requests(),
        keys_per_call=6,
        max_retries=2,
        base_delay=0,
    )
    assert result.storage_root == bytes(STORAGE_ROOT)
    assert set(result.proofs) == set(_user_requests()[:2])
    assert set(result.errors) == set(_user_requests()[2:])
    assert all(
        "storageHash mismatch" in str(e) for e in result.errors.values()
    )
    assert result.stats.splits == 1
    # 1 (chunk A) + 1 (chunk B) + 2 singletons x 2 attempts
    assert web3.eth.calls == 6


def test_singleton_validation_failure_is_retried():
    # A singleton whose first answer disagrees on the root and whose second
    # answer agrees must succeed: the retry covers the validation, not only
    # the transport.
    web3 = FakeWeb3([STORAGE_ROOT, OTHER_ROOT, STORAGE_ROOT])
    requests = _user_requests()[:2]
    result = generate_proofs_bulk(
        web3,
        "curve",
        BLOCK,
        requests,
        keys_per_call=3,
        max_retries=2,
        base_delay=0,
    )
    assert not result.errors
    assert set(result.proofs) == set(requests)
    assert web3.eth.calls == 3


def test_missing_storage_hash_is_tolerated_and_flagged():
    class NoRootEth(FakeEth):
        def get_proof(self, address, keys, block):
            response = super().get_proof(address, keys, block)
            del response["storageHash"]
            return response

    web3 = FakeWeb3()
    web3.eth = NoRootEth()
    result = generate_proofs_bulk(web3, "curve", BLOCK, _user_requests())
    assert not result.errors
    assert result.storage_root is None
    assert result.saw_missing_storage_root
    assert len(result.node_stacks) == len(USERS)


def test_mixed_missing_storage_hash_is_flagged():
    class SometimesNoRootEth(FakeEth):
        def get_proof(self, address, keys, block):
            response = super().get_proof(address, keys, block)
            if self.calls == 1:  # first call answered without a root
                del response["storageHash"]
            return response

    web3 = FakeWeb3()
    web3.eth = SometimesNoRootEth()
    result = generate_proofs_bulk(
        web3, "curve", BLOCK, _user_requests(), keys_per_call=6
    )
    assert not result.errors
    assert result.storage_root == bytes(STORAGE_ROOT)  # pinned by call 2
    assert result.saw_missing_storage_root  # ...but call 1 vouched for nothing


def test_malformed_singleton_response_is_retried():
    class FlakyShapeEth(FakeEth):
        def get_proof(self, address, keys, block):
            response = super().get_proof(address, keys, block)
            if self.calls == 1:
                del response["storageProof"]  # malformed once
            return response

    web3 = FakeWeb3()
    web3.eth = FlakyShapeEth()
    requests = _user_requests()[:1]
    result = generate_proofs_bulk(
        web3, "curve", BLOCK, requests, max_retries=2, base_delay=0
    )
    assert not result.errors
    assert set(result.proofs) == set(requests)
    assert web3.eth.calls == 2


def test_bag_from_kept_stacks_deduplicates_shared_root():
    result = generate_proofs_bulk(FakeWeb3(), "curve", BLOCK, _user_requests())
    stacks = [
        s for request in _user_requests() for s in result.node_stacks[request]
    ]
    bag = encode_node_bag(stacks)
    nodes = [rlp.encode(node) for node in rlp.decode(bag)]
    # 12 stacks share one root: 1 + 12 branches + 12 leaves unique nodes.
    assert len(nodes) == 1 + 2 * 12


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


def test_manager_exposes_stacks_and_storage_root(proof_manager):
    proof_manager.web3_service.w3 = FakeWeb3()
    result = proof_manager.get_proofs_bulk(
        protocol="curve",
        block_number=BLOCK,
        gauge_epochs=[(GAUGE, EPOCH)],
        users=[(GAUGE, user) for user in USERS],
    )
    assert result.success
    data = result.data
    assert data.storage_root == bytes(STORAGE_ROOT)
    assert data.saw_missing_storage_root is False
    assert set(data.user_nodes) == {(GAUGE.lower(), u.lower()) for u in USERS}
    assert all(len(stacks) == 3 for stacks in data.user_nodes.values())
    gauge_stack = data.gauge_nodes[(GAUGE.lower(), EPOCH)]
    assert len(gauge_stack) == 3 and all(
        isinstance(n, bytes) for n in gauge_stack
    )
