"""Malformed RPC responses recover through the real Web3 provider/middleware.

The local provider uses the recorded Curve storage paths and a canonical
account leaf containing their root. No network or fabricated storage paths.
"""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
import rlp
from hexbytes import HexBytes
from web3 import Web3
from web3.providers.base import BaseProvider

from votemarket_toolkit.proofs.generators.bulk_proof import (
    ProofRequest,
    ProofResponseMismatch,
    generate_proofs_bulk,
    get_gauge_proof_slots,
    get_user_proof_slots,
)

CONTROLLER = "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB"
GAUGE = "0x26f7786de3e6d9bd37fcf47be6f2bc455a21b74a"
EPOCH = 1730937600
BLOCK = 21134723
FIXTURE = (
    Path(__file__).parent.parent
    / "fixtures/batch_verifier/curve_1730937600_mpt_proof.json"
)


def _stacks(blob):
    return [
        ["0x" + rlp.encode(node).hex() for node in stack]
        for stack in rlp.decode(HexBytes(blob))
    ]


class FixtureProvider(BaseProvider):
    def __init__(self, mutation=None, persistent=False):
        super().__init__()
        fixture = json.loads(FIXTURE.read_text())
        point_stack = _stacks(fixture["point_data_proof"])[0]
        self.storage_root = bytes(Web3.keccak(HexBytes(point_stack[0])))
        code_hash = bytes(Web3.keccak(b""))
        account = rlp.encode([b"", b"", self.storage_root, code_hash])
        account_node = rlp.encode(
            [b"\x20" + bytes(Web3.keccak(HexBytes(CONTROLLER))), account]
        )
        self.common = {
            "address": CONTROLLER,
            "balance": "0x0",
            "nonce": "0x0",
            "codeHash": "0x" + code_hash.hex(),
            "storageHash": "0x" + self.storage_root.hex(),
            "accountProof": ["0x" + account_node.hex()],
        }
        self.paths = {
            int(
                get_gauge_proof_slots("curve", GAUGE, EPOCH)[0], 16
            ): point_stack
        }
        self.requests = [ProofRequest.for_gauge(GAUGE, EPOCH)]
        for user, data in fixture["users"].items():
            self.requests.append(ProofRequest.for_user(GAUGE, user))
            slots = get_user_proof_slots("curve", GAUGE, user)
            for key, stack in zip(slots, _stacks(data["storage_proof"])):
                self.paths[int(key, 16)] = stack
        self.mutation = mutation
        self.persistent = persistent
        self.calls = 0

    def make_request(self, method, params):
        assert method == "eth_getProof"
        assert params[0] == Web3.to_checksum_address(CONTROLLER)
        assert params[2] == hex(BLOCK)
        self.calls += 1
        result = deepcopy(self.common)
        result["storageProof"] = [
            {"key": key, "value": "0x0", "proof": self.paths[int(key, 16)]}
            for key in params[1]
        ]
        if self.mutation and (self.calls == 1 or self.persistent):
            result = self.mutation(deepcopy(result))
        return {"jsonrpc": "2.0", "id": self.calls, "result": result}


@pytest.fixture(autouse=True)
def _static_controller():
    with patch(
        "votemarket_toolkit.shared.registry.get_gauge_controller",
        return_value=CONTROLLER,
    ):
        yield


def _replace(path, value):
    def mutate(response):
        if not path:
            return value
        target = response
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return response

    return mutate


def _remove(path):
    def mutate(response):
        target = response
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]
        return response

    return mutate


MALFORMED = {
    "response_null": _replace([], None),
    "response_list": _replace([], []),
    "account_missing": _remove(["accountProof"]),
    "account_null": _replace(["accountProof"], None),
    "account_integer": _replace(["accountProof"], 42),
    "account_string": _replace(["accountProof"], "0xc0"),
    "account_object": _replace(["accountProof"], {}),
    "account_bad_hex": _replace(["accountProof"], ["0xzz"]),
    "account_bad_rlp": _replace(["accountProof"], ["0x81"]),
    "account_rlp_scalar": _replace(["accountProof"], ["0x01"]),
    "storage_missing": _remove(["storageProof"]),
    "storage_null": _replace(["storageProof"], None),
    "storage_integer": _replace(["storageProof"], 42),
    "storage_string": _replace(["storageProof"], "0xc0"),
    "storage_object": _replace(["storageProof"], {}),
    "storage_wrong_count": _replace(["storageProof"], []),
    "entry_null": _replace(["storageProof", 0], None),
    "entry_integer": _replace(["storageProof", 0], 42),
    "entry_list": _replace(["storageProof", 0], []),
    "key_missing": _remove(["storageProof", 0, "key"]),
    "key_null": _replace(["storageProof", 0, "key"], None),
    "key_bad_hex": _replace(["storageProof", 0, "key"], "0xzz"),
    "key_empty": _replace(["storageProof", 0, "key"], "0x"),
    "key_oversize": _replace(["storageProof", 0, "key"], "0x" + "11" * 33),
    "proof_missing": _remove(["storageProof", 0, "proof"]),
    "proof_null": _replace(["storageProof", 0, "proof"], None),
    "proof_integer": _replace(["storageProof", 0, "proof"], 42),
    "proof_string": _replace(["storageProof", 0, "proof"], "0xc0"),
    "proof_object": _replace(["storageProof", 0, "proof"], {}),
    "node_null": _replace(["storageProof", 0, "proof"], [None]),
    "node_integer": _replace(["storageProof", 0, "proof"], [42]),
    "node_bad_hex": _replace(["storageProof", 0, "proof"], ["0xzz"]),
    "node_unprefixed_hex": _replace(["storageProof", 0, "proof"], ["c0"]),
    "node_spaced_hex": _replace(["storageProof", 0, "proof"], ["0xc0 00"]),
    "node_odd_hex": _replace(["storageProof", 0, "proof"], ["0xc00"]),
    "node_bad_rlp": _replace(["storageProof", 0, "proof"], ["0x81"]),
    "node_rlp_scalar": _replace(["storageProof", 0, "proof"], ["0x01"]),
    "root_null": _replace(["storageHash"], None),
    "root_integer": _replace(["storageHash"], 42),
    "root_empty": _replace(["storageHash"], "0x"),
    "root_short": _replace(["storageHash"], "0xabcdef"),
    "root_long": _replace(["storageHash"], "0x" + "11" * 33),
    "root_bad_hex": _replace(["storageHash"], "0xzz"),
    "root_list": _replace(["storageHash"], []),
    "root_odd_hex": _replace(["storageHash"], "0x" + "1" * 63),
}


@pytest.mark.parametrize("case", MALFORMED)
def test_malformed_response_retries_then_matches_valid_bytes(case):
    reference = FixtureProvider()
    request = reference.requests[1]
    expected = generate_proofs_bulk(Web3(reference), "curve", BLOCK, [request])
    provider = FixtureProvider(MALFORMED[case])

    result = generate_proofs_bulk(
        Web3(provider), "curve", BLOCK, [request], max_retries=2, base_delay=0
    )

    assert provider.calls == 2
    assert result.errors == {}
    assert result.proofs == expected.proofs
    assert result.node_stacks == expected.node_stacks
    assert result.storage_root == reference.storage_root
    assert result.saw_missing_storage_root is False


@pytest.mark.parametrize("case", MALFORMED)
def test_persistent_malformed_response_keeps_no_state(case):
    provider = FixtureProvider(MALFORMED[case], persistent=True)
    request = provider.requests[1]

    result = generate_proofs_bulk(
        Web3(provider), "curve", BLOCK, [request], max_retries=2, base_delay=0
    )

    assert provider.calls == 2
    assert isinstance(result.errors[request], ProofResponseMismatch)
    assert result.proofs == result.node_stacks == {}
    assert result.storage_root is None
    assert result.saw_missing_storage_root is False


def test_short_first_root_recovers_and_all_following_chunks_continue():
    provider = FixtureProvider(MALFORMED["root_short"])
    result = generate_proofs_bulk(
        Web3(provider),
        "curve",
        BLOCK,
        provider.requests,
        keys_per_call=3,
        max_retries=2,
        base_delay=0,
        abort_after_failures=2,
    )
    assert provider.calls == len(provider.requests) + 1
    assert (
        set(result.proofs) == set(result.node_stacks) == set(provider.requests)
    )
    assert result.errors == {}
    assert result.storage_root == provider.storage_root
    assert result.stats.aborted is False


@pytest.mark.parametrize("missing_root", [False, True])
def test_bad_late_entry_does_not_commit_root_or_missing_flag(missing_root):
    def malformed(response):
        if missing_root:
            del response["storageHash"]
        else:
            response["storageHash"] = "0x" + "33" * 32
        response["storageProof"][-1]["proof"] = ["0x81"]
        return response

    provider = FixtureProvider(malformed)
    reference = FixtureProvider()
    expected = generate_proofs_bulk(
        Web3(reference), "curve", BLOCK, reference.requests
    )
    result = generate_proofs_bulk(
        Web3(provider),
        "curve",
        BLOCK,
        provider.requests,
        max_retries=2,
        base_delay=0,
    )
    assert result.stats.splits == 1
    assert provider.calls == 3
    assert result.proofs == expected.proofs
    assert result.node_stacks == expected.node_stacks
    assert result.storage_root == provider.storage_root
    assert result.saw_missing_storage_root is False
    assert result.errors == {}


def test_internal_encoder_error_is_not_relabelled_or_retried():
    provider = FixtureProvider()
    request = provider.requests[1]
    with patch(
        "votemarket_toolkit.proofs.generators.bulk_proof.rlp.encode",
        side_effect=TypeError("internal encoder bug"),
    ):
        result = generate_proofs_bulk(
            Web3(provider),
            "curve",
            BLOCK,
            [request],
            max_retries=3,
            base_delay=0,
        )
    assert provider.calls == 1
    assert type(result.errors[request]) is TypeError
    assert str(result.errors[request]) == "internal encoder bug"
    assert result.proofs == result.node_stacks == {}
    assert result.storage_root is None


@pytest.mark.parametrize("error_type", [TypeError, ValueError])
def test_internal_provider_error_is_not_relabelled_or_retried(error_type):
    provider = FixtureProvider()
    request = provider.requests[1]
    with patch.object(
        provider,
        "make_request",
        side_effect=error_type("internal provider bug"),
    ) as call:
        result = generate_proofs_bulk(
            Web3(provider),
            "curve",
            BLOCK,
            [request],
            max_retries=3,
            base_delay=0,
        )
    assert call.call_count == 1
    assert type(result.errors[request]) is error_type
    assert str(result.errors[request]) == "internal provider bug"
    assert result.proofs == result.node_stacks == {}
    assert result.storage_root is None
