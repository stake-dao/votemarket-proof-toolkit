"""
Unit tests for the batch-verifier artifacts attached to the published proofs.
"""

import rlp

from votemarket_toolkit.proofs.batch_artifacts import (
    BatchStacks,
    attach_batch_artifacts,
    gauge_accounts,
    safe_attach_batch_artifacts,
    strip_batch_artifacts,
)
from votemarket_toolkit.proofs.generators.node_bag import (
    ACCOUNT_CALL_HEAD_BYTES,
    calldata_size,
    encode_node_bag,
    node_bag_size,
)

GAUGE = "0xd5f2e6612e41be48461fdba20061e3c778fe6ec4"
OTHER_GAUGE = "0x7e1444ba99dcdffe8fbdb42c02fb0da4aaace4d5"
ROOT = b"\x42" * 32
BLOCK = 21000000
OTHER_BLOCK = 21000100


def _stack(tag: bytes, depth: int = 3):
    return [rlp.encode([b"shared-root", b"\x00" * 40])] + [
        rlp.encode([tag, b"node", bytes([i]), b"\x00" * 40])
        for i in range(depth - 1)
    ]


def _user_stacks(user: str, block: int = BLOCK):
    return [
        _stack(user.encode() + block.to_bytes(4, "big") + bytes([k]))
        for k in range(3)
    ]


def _stacks(users, gauge=GAUGE, root=ROOT, block=BLOCK):
    stacks = BatchStacks()
    stacks.record(
        block,
        {(gauge, u): _user_stacks(u, block) for u in users},
        {(gauge, 1764806400): _stack(b"point" + gauge.encode())},
        root,
    )
    return stacks


def _platform(users, listed=None, gauge=GAUGE, block=BLOCK):
    return {
        "block_data": {"block_number": block},
        "gauges": {
            gauge: {
                "point_data_proof": "0x",
                "users": {u: {"storage_proof": "0x"} for u in users},
                "listed_users": {
                    "0xplatform-1": {
                        u: {"storage_proof": "0x"} for u in (listed or [])
                    }
                },
            }
        },
    }


def test_gauge_accounts_are_sorted_lowercase_deduplicated():
    gauge_data = {
        "users": {"0xBB": {}, "0xaa": {}},
        "listed_users": {"c1": {"0xbb": {}, "0xDD": {}}, "c2": {"0xcc": {}}},
    }
    assert gauge_accounts(gauge_data) == ["0xaa", "0xbb", "0xcc", "0xdd"]


def test_artifacts_attached_for_supported_protocol():
    users = ["0xa1", "0xa2", "0xa3"]
    platform = _platform(users[:2], listed=users[2:])
    summary = attach_batch_artifacts(
        platform, "curve", 42161, BLOCK, _stacks(users)
    )

    assert summary.gauges == 1 and summary.account_chunks == 1
    assert not summary.skipped
    batch = platform["gauges"][GAUGE]["batch"]
    assert batch["version"] == 1
    assert batch["observed_storage_root"] == "0x" + ROOT.hex()
    assert batch["block_number"] == BLOCK
    assert batch["accounts_total"] == 3
    chunk = batch["chunks"][0]
    assert chunk["accounts"] == sorted(users)
    expected = encode_node_bag(
        [s for u in sorted(users) for s in _user_stacks(u)]
    )
    assert chunk["node_bag"] == "0x" + expected.hex()
    assert chunk["bag_bytes"] == len(expected)
    assert chunk["calldata_bytes"] == calldata_size(
        ACCOUNT_CALL_HEAD_BYTES, 3, len(expected)
    )

    points = platform["batch_points"]
    assert points["chunks"][0]["gauges"] == [GAUGE]
    assert points["missing_gauges"] == []
    assert (
        points["chunks"][0]["node_bag"]
        == "0x" + encode_node_bag([_stack(b"point" + GAUGE.encode())]).hex()
    )
    assert summary.point_chunks == 1
    # Legacy fields are untouched.
    assert platform["gauges"][GAUGE]["users"] == {
        u: {"storage_proof": "0x"} for u in users[:2]
    }


def test_chunks_follow_calldata_budget():
    users = [f"0x{i:02x}" for i in range(6)]
    stacks = _stacks(users)
    budget = calldata_size(
        ACCOUNT_CALL_HEAD_BYTES,
        2,
        node_bag_size(_user_stacks(users[0]) + _user_stacks(users[1])),
    )
    platform = _platform(users)
    summary = attach_batch_artifacts(
        platform, "balancer", 10, BLOCK, stacks, max_bytes=budget
    )

    chunks = platform["gauges"][GAUGE]["batch"]["chunks"]
    assert summary.account_chunks == len(chunks) == 3
    assert [a for c in chunks for a in c["accounts"]] == sorted(users)
    assert all(c["calldata_bytes"] <= budget for c in chunks)


def test_unsupported_protocol_gets_nothing():
    platform = _platform(["0xa1"])
    summary = attach_batch_artifacts(
        platform, "pendle", 42161, BLOCK, _stacks(["0xa1"])
    )
    assert "batch" not in platform["gauges"][GAUGE]
    assert "batch_points" not in platform
    assert summary.skipped and "not supported" in summary.skipped[0]


def test_conflicting_storage_roots_fail_closed():
    stacks = _stacks(["0xa1"])
    stacks.record(BLOCK, {}, {}, b"\x24" * 32)  # a later run disagrees
    assert BLOCK in stacks.conflicting_blocks
    platform = _platform(["0xa1"])
    summary = attach_batch_artifacts(platform, "curve", 42161, BLOCK, stacks)
    assert "batch" not in platform["gauges"][GAUGE]
    assert "conflicting storage roots" in summary.skipped[0]


def test_missing_storage_root_fails_closed():
    platform = _platform(["0xa1"])
    summary = attach_batch_artifacts(
        platform, "curve", 42161, BLOCK, _stacks(["0xa1"], root=None)
    )
    assert "batch" not in platform["gauges"][GAUGE]
    assert "batch_points" not in platform
    assert "no storage root" in summary.skipped[0]


def test_stacks_are_keyed_by_block():
    # Nodes recorded at another block must not serve this platform's block.
    stacks = _stacks(["0xa1"], block=OTHER_BLOCK)
    platform = _platform(["0xa1"], block=BLOCK)
    summary = attach_batch_artifacts(platform, "curve", 42161, BLOCK, stacks)
    assert "batch" not in platform["gauges"][GAUGE]
    assert "batch_points" not in platform
    assert "without trie nodes at block" in summary.skipped[0]

    # Two blocks coexist in one collector, each with its own root.
    stacks.record(
        BLOCK, {(GAUGE, "0xa1"): _user_stacks("0xa1")}, {}, b"\x01" * 32
    )
    assert stacks.storage_roots == {OTHER_BLOCK: ROOT, BLOCK: b"\x01" * 32}
    assert not stacks.conflicting_blocks
    platform = _platform(["0xa1"], block=BLOCK)
    attach_batch_artifacts(platform, "curve", 42161, BLOCK, stacks)
    assert platform["gauges"][GAUGE]["batch"]["observed_storage_root"] == (
        "0x" + "01" * 32
    )


def test_partial_coverage_omits_the_gauge_batch():
    # One published account without nodes: no batch at all for the gauge
    # (a partial batch would hide legacy accounts from the consumer).
    platform = _platform(["0xa1", "0xa2"])
    summary = attach_batch_artifacts(
        platform, "fxn", 10, BLOCK, _stacks(["0xa1"])
    )
    assert "batch" not in platform["gauges"][GAUGE]
    assert any(
        "1/2 account(s) without trie nodes" in s for s in summary.skipped
    )
    assert platform["batch_points"]["chunks"][0]["gauges"] == [GAUGE]


def test_point_artifact_names_gauges_without_nodes():
    stacks = _stacks(["0xa1"], gauge=GAUGE)
    platform = _platform(["0xa1"], gauge=GAUGE)
    platform["gauges"][OTHER_GAUGE] = {"point_data_proof": "0x", "users": {}}
    attach_batch_artifacts(platform, "curve", 42161, BLOCK, stacks)
    assert platform["batch_points"]["chunks"][0]["gauges"] == [GAUGE]
    assert platform["batch_points"]["missing_gauges"] == [OTHER_GAUGE]


def test_account_over_budget_skips_gauge_but_reports():
    platform = _platform(["0xa1"])
    summary = attach_batch_artifacts(
        platform, "curve", 42161, BLOCK, _stacks(["0xa1"]), max_bytes=10
    )
    assert "batch" not in platform["gauges"][GAUGE]
    assert "batch_points" not in platform
    assert len(summary.skipped) == 2


def test_safe_wrapper_never_breaks_legacy_publication(monkeypatch):
    import votemarket_toolkit.proofs.batch_artifacts as module

    platform = _platform(["0xa1"])
    platform["gauges"][GAUGE]["batch"] = {"stale": True}

    def _boom(*args, **kwargs):
        platform["batch_points"] = {"partial": True}
        raise RuntimeError("provider key sk-secret exploded")

    monkeypatch.setattr(module, "attach_batch_artifacts", _boom)
    summary = safe_attach_batch_artifacts(
        platform, "curve", 42161, BLOCK, _stacks(["0xa1"])
    )
    assert "batch" not in platform["gauges"][GAUGE]
    assert "batch_points" not in platform
    assert platform["gauges"][GAUGE]["users"] == {
        "0xa1": {"storage_proof": "0x"}
    }
    assert summary.skipped and "internal error" in summary.skipped[0]


def test_safe_wrapper_rejects_bad_block_number_gracefully():
    platform = _platform(["0xa1"])
    summary = safe_attach_batch_artifacts(
        platform, "curve", 42161, "not-a-block", _stacks(["0xa1"])
    )
    assert "batch" not in platform["gauges"][GAUGE]
    assert "internal error" in summary.skipped[0]


def test_record_normalizes_addresses():
    stacks = BatchStacks()
    stacks.record(
        BLOCK,
        {(GAUGE.upper(), "0xAB"): _user_stacks("0xab")},
        {(OTHER_GAUGE.upper(), 1): _stack(b"p")},
        ROOT,
    )
    assert (BLOCK, GAUGE.lower(), "0xab") in stacks.user_stacks
    assert (BLOCK, OTHER_GAUGE.lower()) in stacks.point_stacks


def test_stale_artifacts_are_replaced_or_removed():
    # Whatever artifacts an entry carries, attaching for a block ends with
    # exactly that block's artifacts — or none when the block is unusable.
    platform = _platform(["0xa1"])
    platform["gauges"][GAUGE]["batch"] = {"stale": True}
    platform["batch_points"] = {"stale": True}
    attach_batch_artifacts(platform, "curve", 42161, BLOCK, _stacks(["0xa1"]))
    assert platform["gauges"][GAUGE]["batch"]["block_number"] == BLOCK
    assert platform["batch_points"]["block_number"] == BLOCK

    attach_batch_artifacts(
        platform, "curve", 42161, OTHER_BLOCK, _stacks(["0xa1"])
    )
    assert "batch" not in platform["gauges"][GAUGE]
    assert "batch_points" not in platform


def test_mixed_missing_storage_hash_fails_closed():
    stacks = _stacks(["0xa1"])
    # A later run at the same block had a response without storageHash.
    stacks.record(
        BLOCK,
        {(GAUGE, "0xa2"): _user_stacks("0xa2")},
        {},
        ROOT,
        saw_missing_root=True,
    )
    platform = _platform(["0xa1", "0xa2"])
    summary = attach_batch_artifacts(platform, "curve", 42161, BLOCK, stacks)
    assert "batch" not in platform["gauges"][GAUGE]
    assert "no storage root" in summary.skipped[0]


def test_point_chunks_are_canonical_across_gauge_order():
    stacks = BatchStacks()
    for gauge in (OTHER_GAUGE, GAUGE):
        stacks.record(
            BLOCK, {}, {(gauge, 1): _stack(b"p" + gauge.encode())}, ROOT
        )
    forward = {
        "block_data": {"block_number": BLOCK},
        "gauges": {GAUGE: {"users": {}}, OTHER_GAUGE: {"users": {}}},
    }
    backward = {
        "block_data": {"block_number": BLOCK},
        "gauges": {OTHER_GAUGE: {"users": {}}, GAUGE: {"users": {}}},
    }
    attach_batch_artifacts(forward, "curve", 42161, BLOCK, stacks)
    attach_batch_artifacts(backward, "curve", 42161, BLOCK, stacks)
    assert forward["batch_points"] == backward["batch_points"]
    assert forward["batch_points"]["chunks"][0]["gauges"] == sorted(
        [GAUGE, OTHER_GAUGE]
    )


def test_platforms_sharing_a_gauge_object_get_their_own_artifacts():
    # The script stores the same cached gauge dict in every platform that
    # uses the gauge, while platforms may anchor different blocks.
    shared = {
        "point_data_proof": "0x",
        "users": {"0xa1": {"storage_proof": "0x"}},
        "listed_users": {},
    }
    platform_a = {
        "block_data": {"block_number": BLOCK},
        "gauges": {GAUGE: shared},
    }
    platform_b = {
        "block_data": {"block_number": OTHER_BLOCK},
        "gauges": {GAUGE: shared},
    }
    stacks = _stacks(["0xa1"], block=BLOCK)  # nodes exist for block A only

    summary_a = safe_attach_batch_artifacts(
        platform_a, "curve", 42161, BLOCK, stacks
    )
    summary_b = safe_attach_batch_artifacts(
        platform_b, "curve", 42161, OTHER_BLOCK, stacks
    )

    assert summary_a.gauges == 1
    assert platform_a["gauges"][GAUGE]["batch"]["block_number"] == BLOCK
    assert (
        "batch" not in platform_b["gauges"][GAUGE]
    ), "B must not inherit A's batch"
    assert any("without trie nodes at block" in r for r in summary_b.skipped)
    # The shared cached object itself is never touched.
    assert "batch" not in shared
    assert platform_a["gauges"][GAUGE] is not shared
    assert (
        platform_a["gauges"][GAUGE]["users"] is shared["users"]
    )  # legacy data still shared


def test_platform_not_at_header_block_gets_no_artifacts():
    platform = _platform(["0xa1"], block=OTHER_BLOCK)
    stacks = _stacks(["0xa1"], block=OTHER_BLOCK)
    summary = safe_attach_batch_artifacts(
        platform, "curve", 42161, OTHER_BLOCK, stacks, header_block=BLOCK
    )
    assert "batch" not in platform["gauges"][GAUGE]
    assert "batch_points" not in platform
    assert "published header is for block" in summary.skipped[0]

    summary = safe_attach_batch_artifacts(
        platform,
        "curve",
        42161,
        OTHER_BLOCK,
        stacks,
        header_block=str(OTHER_BLOCK),
    )
    assert summary.gauges == 1


def test_safe_wrapper_is_idempotent():
    platform = _platform(["0xa1"])
    stacks = _stacks(["0xa1"])
    first = safe_attach_batch_artifacts(
        platform, "curve", 42161, BLOCK, stacks
    )
    snapshot = json_copy(platform)
    second = safe_attach_batch_artifacts(
        platform, "curve", 42161, BLOCK, stacks
    )
    assert first.gauges == second.gauges == 1
    assert json_copy(platform) == snapshot


def test_strip_batch_artifacts_keeps_legacy_fields():
    platform = _platform(["0xa1"])
    platform["gauges"][GAUGE]["batch"] = {"x": 1}
    platform["batch_points"] = {"x": 1}
    strip_batch_artifacts(platform)
    assert "batch" not in platform["gauges"][GAUGE]
    assert "batch_points" not in platform
    assert platform["gauges"][GAUGE]["users"] == {
        "0xa1": {"storage_proof": "0x"}
    }


def json_copy(value):
    import json

    return json.loads(json.dumps(value))
