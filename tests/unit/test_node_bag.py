"""
Unit tests for node bags (batched storage proofs for the BatchVerifier).

The encoder must produce, byte for byte, the bags that the Solidity reference
helper ``test/utils/BagBuilder.sol`` builds in ``contracts-monorepo``: the
golden keccak values below are logged by ``test_accountBatch_matchesLegacyVerifier``
and ``test_pointBatch_matchesLegacyVerifier`` in
``packages/votemarket/test/unit/oracle/BatchVerifier.t.sol`` on the same
recorded fixture (Curve gauge controller, epoch 1730937600, 5 accounts).
"""

import json
from pathlib import Path
from typing import Dict, List

import pytest
import rlp
from eth_utils import keccak
from hexbytes import HexBytes

from votemarket_toolkit.proofs.generators.node_bag import (
    ACCOUNT_CALL_HEAD_BYTES,
    CALLDATA_MAX_BYTES_BY_CHAIN,
    DEFAULT_CALLDATA_MAX_BYTES,
    EMBEDDED_NODE_MAX_BYTES,
    POINT_CALL_HEAD_BYTES,
    BagChunk,
    batch_artifact,
    calldata_max_bytes,
    calldata_size,
    chunk_by_calldata_size,
    encode_node_bag,
    node_bag_size,
    normalize_stack,
    supports_batch_verifier,
    unique_nodes,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "batch_verifier"
    / "curve_1730937600_mpt_proof.json"
)

# keccak256 of the bags built by BagBuilder.buildBag on the fixture (Solidity).
GOLDEN_BAG_5_ACCOUNTS = (
    "0x6ae9065861e5ad98e4dbe670957ec9e939a276279081858b229df5fec534ea34"
)
GOLDEN_BAG_5_ACCOUNTS_BYTES = 21846
GOLDEN_BAG_ACCOUNTS_0_1 = (
    "0xa74ea89368b56a7baa922dbbfecb6891c3469a801b0a991f0245ed6785931e59"
)
GOLDEN_POINT_BAG = (
    "0x5f7bc7cafa91068bfc041a70b4b785d8be0fb1829a3a2818cf829ae2603a9e38"
)


def _stacks_from_blob(blob_hex: str) -> List[List[bytes]]:
    """Legacy blob ``RLP([[node...], [node...], ...])`` -> raw node bytes per stack.

    Re-encoding each decoded node gives back its canonical RLP encoding, i.e.
    the exact bytes ``eth_getProof`` returned (what BagBuilder's ``toRlpBytes``
    re-emits on the Solidity side).
    """
    return [
        [rlp.encode(node) for node in stack]
        for stack in rlp.decode(bytes(HexBytes(blob_hex)))
    ]


@pytest.fixture(scope="module")
def fixture() -> Dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture(scope="module")
def user_stacks(fixture) -> Dict[str, List[List[bytes]]]:
    """{user: [lastVote stack, slope stack, end stack]} in fixture order."""
    return {
        user: _stacks_from_blob(entry["storage_proof"])
        for user, entry in fixture["users"].items()
    }


# =============================================================================
# 1. Parity with the Solidity reference (golden values)
# =============================================================================


def test_bag_matches_bag_builder_for_all_accounts(user_stacks):
    stacks = [stack for stacks in user_stacks.values() for stack in stacks]
    bag = encode_node_bag(stacks)
    assert len(bag) == GOLDEN_BAG_5_ACCOUNTS_BYTES
    assert "0x" + keccak(bag).hex() == GOLDEN_BAG_5_ACCOUNTS


def test_bag_matches_bag_builder_for_first_two_accounts(user_stacks):
    users = list(user_stacks)[:2]
    stacks = [stack for user in users for stack in user_stacks[user]]
    assert (
        "0x" + keccak(encode_node_bag(stacks)).hex() == GOLDEN_BAG_ACCOUNTS_0_1
    )


def test_point_bag_matches_bag_builder(fixture):
    stacks = _stacks_from_blob(fixture["point_data_proof"])
    assert len(stacks) == 1
    assert "0x" + keccak(encode_node_bag(stacks)).hex() == GOLDEN_POINT_BAG


def test_bag_is_order_independent(user_stacks):
    stacks = [stack for stacks in user_stacks.values() for stack in stacks]
    assert encode_node_bag(list(reversed(stacks))) == encode_node_bag(stacks)


# =============================================================================
# 2. Bag contract: framing, strict ordering, embedded nodes
# =============================================================================


def test_bag_is_one_rlp_list_of_unique_nodes_sorted_by_keccak(user_stacks):
    stacks = [stack for stacks in user_stacks.values() for stack in stacks]
    bag = encode_node_bag(stacks)

    decoded = rlp.decode(bag)
    nodes = [rlp.encode(node) for node in decoded]
    assert b"".join(nodes) == bag[len(bag) - len(b"".join(nodes)) :]
    hashes = [keccak(node) for node in nodes]
    assert hashes == sorted(hashes)
    assert len(set(hashes)) == len(hashes)
    assert set(hashes) == set(unique_nodes(stacks))


def test_shared_upper_levels_are_deduplicated(user_stacks):
    stacks = [stack for stacks in user_stacks.values() for stack in stacks]
    total_nodes = sum(len(stack) for stack in stacks)
    assert len(unique_nodes(stacks)) < total_nodes
    assert len(encode_node_bag(stacks)) < sum(
        len(node) for stack in stacks for node in stack
    )


def test_embedded_nodes_are_dropped_except_stack_roots():
    root = rlp.encode([b"r" * 40, b""])  # a 32+ byte root
    short_root = rlp.encode([b"s"])  # tiny trie: root shorter than 32 bytes
    embedded = rlp.encode([b"e", b"f"])  # < 32 bytes, inlined in its parent
    leaf = rlp.encode([b"l" * 40, b"value"])
    assert len(embedded) < EMBEDDED_NODE_MAX_BYTES
    assert len(short_root) < EMBEDDED_NODE_MAX_BYTES

    nodes = unique_nodes([[root, embedded, leaf], [short_root]])
    assert keccak(embedded) not in nodes
    assert keccak(short_root) in nodes
    assert keccak(root) in nodes and keccak(leaf) in nodes


def test_node_bag_size_matches_encoding(user_stacks):
    stacks = [stack for stacks in user_stacks.values() for stack in stacks]
    assert node_bag_size(stacks) == len(encode_node_bag(stacks))
    assert (
        node_bag_size([]) == len(encode_node_bag([])) == 1
    )  # empty list 0xc0


def test_long_list_header_encoding(user_stacks):
    stacks = [stack for stacks in user_stacks.values() for stack in stacks]
    bag = encode_node_bag(stacks)
    assert bag[0] >= 0xF8  # payload >= 56 bytes: long-list form
    length_bytes = bag[0] - 0xF7
    payload_len = int.from_bytes(bag[1 : 1 + length_bytes], "big")
    assert 1 + length_bytes + payload_len == len(bag)


@pytest.mark.parametrize(
    "payload_len", [0, 1, 55, 56, 255, 256, 65_535, 65_536]
)
def test_list_header_boundaries(payload_len):
    # One root node whose RLP encoding is exactly payload_len bytes long.
    if payload_len == 0:
        stacks = []
    else:
        inner = payload_len - 1 if payload_len < 57 else payload_len - 3
        if payload_len > 255 + 3:
            inner = payload_len - 4
        node = rlp.encode(b"x" * inner)
        while len(node) != payload_len:
            inner += 1 if len(node) < payload_len else -1
            node = rlp.encode(b"x" * inner)
        stacks = [[node]]
    bag = encode_node_bag(stacks)
    assert len(bag) == node_bag_size(stacks)
    assert [rlp.encode(n) for n in rlp.decode(bag)] == [s[0] for s in stacks]
    if payload_len < 56:
        assert bag[0] == 0xC0 + payload_len
    else:
        length_bytes = bag[0] - 0xF7
        assert int.from_bytes(bag[1 : 1 + length_bytes], "big") == payload_len
        assert length_bytes == (payload_len.bit_length() + 7) // 8


def test_rejects_non_bytes_nodes():
    with pytest.raises(TypeError):
        unique_nodes([["0xabcd"]])


def test_normalize_stack_accepts_hex_and_bytes():
    node = rlp.encode([b"x" * 40])
    assert normalize_stack(["0x" + node.hex(), node, HexBytes(node)]) == [
        node,
        node,
        node,
    ]


# =============================================================================
# 3. Chunking by encoded call size
# =============================================================================


def _call_size(stacks, members=1, head=ACCOUNT_CALL_HEAD_BYTES):
    return calldata_size(head, members, node_bag_size(stacks))


def test_calldata_size_is_head_plus_members_plus_padded_bag():
    assert calldata_size(ACCOUNT_CALL_HEAD_BYTES, 0, 0) == 4 + 6 * 32
    assert calldata_size(POINT_CALL_HEAD_BYTES, 0, 0) == 4 + 5 * 32
    assert calldata_size(0, 3, 1) == 3 * 32 + 32
    assert calldata_size(0, 0, 32) == 32
    assert calldata_size(0, 0, 33) == 64


def test_chunks_respect_budget_cover_all_members_in_order(user_stacks):
    users = list(user_stacks)
    budget = _call_size(user_stacks[users[0]] + user_stacks[users[1]], 2)
    chunks = chunk_by_calldata_size(users, user_stacks, budget)

    assert [member for chunk in chunks for member in chunk.members] == users
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.calldata_bytes <= budget
        own_stacks = [s for m in chunk.members for s in user_stacks[m]]
        # Each chunk's bag is built from its own members only, and the
        # reported size is the encoded call for exactly those members.
        assert chunk.node_bag == encode_node_bag(own_stacks)
        assert chunk.calldata_bytes == calldata_size(
            ACCOUNT_CALL_HEAD_BYTES, len(chunk.members), len(chunk.node_bag)
        )


def test_single_chunk_when_everything_fits(user_stacks):
    users = list(user_stacks)
    chunks = chunk_by_calldata_size(
        users, user_stacks, DEFAULT_CALLDATA_MAX_BYTES
    )
    assert len(chunks) == 1
    assert chunks[0].members == users
    assert "0x" + keccak(chunks[0].node_bag).hex() == GOLDEN_BAG_5_ACCOUNTS


def test_budget_exactly_equal_is_accepted(user_stacks):
    users = list(user_stacks)[:2]
    stacks = [s for u in users for s in user_stacks[u]]
    exact = _call_size(stacks, 2)
    assert len(chunk_by_calldata_size(users, user_stacks, exact)) == 1
    assert len(chunk_by_calldata_size(users, user_stacks, exact - 1)) == 2


def test_cheap_members_are_bounded_by_the_member_word():
    # Exclusion-like members: every member shares the same nodes, so the bag
    # does not grow, but each member still costs one 32-byte calldata word.
    shared = [rlp.encode([b"r" * 40, b""]), rlp.encode([b"l" * 40, b"v"])]
    members = [f"0x{i:040x}" for i in range(50)]
    stacks = {m: [shared] for m in members}
    budget = calldata_size(
        ACCOUNT_CALL_HEAD_BYTES, 10, node_bag_size([shared])
    )
    chunks = chunk_by_calldata_size(members, stacks, budget)
    assert [len(c.members) for c in chunks] == [10, 10, 10, 10, 10]
    assert all(c.calldata_bytes <= budget for c in chunks)


def test_point_head_is_used_for_gauges():
    stack = [rlp.encode([b"r" * 40, b""])]
    chunks = chunk_by_calldata_size(
        ["0xg"], {"0xg": [stack]}, 10_000, POINT_CALL_HEAD_BYTES
    )
    assert chunks[0].calldata_bytes == calldata_size(
        POINT_CALL_HEAD_BYTES, 1, len(chunks[0].node_bag)
    )


def test_member_over_budget_raises(user_stacks):
    users = list(user_stacks)
    too_small = _call_size(user_stacks[users[0]]) - 1
    with pytest.raises(ValueError, match="exceeds"):
        chunk_by_calldata_size(users, user_stacks, too_small)


def test_missing_stacks_raise(user_stacks):
    with pytest.raises(ValueError, match="No proof stacks"):
        chunk_by_calldata_size(
            ["0xunknown"], user_stacks, DEFAULT_CALLDATA_MAX_BYTES
        )


def test_invalid_budget_raises(user_stacks):
    with pytest.raises(ValueError):
        chunk_by_calldata_size(list(user_stacks), user_stacks, 0)


def test_no_members_no_chunks(user_stacks):
    assert (
        chunk_by_calldata_size([], user_stacks, DEFAULT_CALLDATA_MAX_BYTES)
        == []
    )


# =============================================================================
# 4. Artifact and configuration
# =============================================================================


def test_batch_artifact_json(user_stacks):
    users = list(user_stacks)[:2]
    chunks = chunk_by_calldata_size(
        users, user_stacks, DEFAULT_CALLDATA_MAX_BYTES
    )
    artifact = batch_artifact(
        chunks, "accounts", b"\x11" * 32, block_number=123, accounts_total=2
    )
    assert artifact["version"] == 1
    assert artifact["verifier"] == "BatchVerifier"
    assert artifact["observed_storage_root"] == "0x" + "11" * 32
    assert artifact["block_number"] == 123
    assert artifact["accounts_total"] == 2
    chunk = artifact["chunks"][0]
    assert chunk["accounts"] == users
    assert chunk["bag_bytes"] == len(chunks[0].node_bag)
    assert chunk["calldata_bytes"] == chunks[0].calldata_bytes
    assert chunk["node_bag"] == "0x" + chunks[0].node_bag.hex()
    assert batch_artifact([], "gauges", None)["observed_storage_root"] is None


def test_chunk_to_json_uses_member_key():
    chunk = BagChunk(["0xa"], b"\xc0", 229)
    assert chunk.to_json("gauges") == {
        "gauges": ["0xa"],
        "node_bag": "0xc0",
        "bag_bytes": 1,
        "calldata_bytes": 229,
    }


@pytest.mark.parametrize(
    "protocol, expected",
    [
        ("curve", True),
        ("balancer", True),
        ("fxn", True),
        ("FXN", True),
        ("pendle", False),
        ("yb", False),
        ("frax", False),
    ],
)
def test_supports_batch_verifier(protocol, expected):
    assert supports_batch_verifier(protocol) is expected


def test_calldata_budget_per_chain():
    assert calldata_max_bytes(42161) == CALLDATA_MAX_BYTES_BY_CHAIN[42161]
    assert calldata_max_bytes("10") == CALLDATA_MAX_BYTES_BY_CHAIN[10]
    assert calldata_max_bytes(8453) == DEFAULT_CALLDATA_MAX_BYTES
    assert calldata_max_bytes(None) == DEFAULT_CALLDATA_MAX_BYTES
    assert CALLDATA_MAX_BYTES_BY_CHAIN[42161] < 95_000
    assert CALLDATA_MAX_BYTES_BY_CHAIN[10] < 131_072
