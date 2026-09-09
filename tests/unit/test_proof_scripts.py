"""Script regressions using local services and recorded Curve proofs only."""

import importlib.util
import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.curve_fixture import (
    BLOCK,
    CONTROLLER,
    EPOCH,
    GAUGE,
    POINT_SLOT,
    USER,
    RecordedCurveProvider,
)
from votemarket_toolkit.proofs import batch_artifacts
from votemarket_toolkit.proofs.generators.node_bag import POINT_CALL_HEAD_BYTES
from votemarket_toolkit.shared.results import Result

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(
        f"{name}_under_test", SCRIPTS / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("Network is forbidden in proof script tests")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def active_script(monkeypatch):
    monkeypatch.setattr(
        "votemarket_toolkit.campaigns.CampaignService", SimpleNamespace
    )
    monkeypatch.setattr(
        "votemarket_toolkit.data.EligibilityService",
        lambda chain_id: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "votemarket_toolkit.proofs.VoteMarketProofs",
        lambda chain_id: SimpleNamespace(),
    )
    return load_script("vm_active_proofs")


@pytest.mark.parametrize(
    "end,closed,remaining,expected",
    [
        (EPOCH + 604800, False, 0, True),
        (EPOCH + 604800, False, 3, True),
        (EPOCH, False, 3, False),
        (EPOCH - 1, False, 3, False),
        (EPOCH + 604800, True, 3, False),
    ],
)
def test_campaign_activity_uses_requested_epoch(
    active_script, end, closed, remaining, expected
):
    campaign = {
        "campaign": {"end_timestamp": end},
        "is_closed": closed,
        "remaining_periods": remaining,
    }
    assert active_script.is_campaign_active(campaign, EPOCH) is expected


@pytest.fixture
def comparison_script(active_script, monkeypatch):
    monkeypatch.setitem(sys.modules, "vm_active_proofs", active_script)
    return load_script("compare_bulk_proofs")


@pytest.mark.asyncio
async def test_comparison_selection_passes_requested_epoch(
    comparison_script, monkeypatch
):
    other_gauge = "0x" + "11" * 20
    campaigns = [
        {
            "campaign": {"gauge": GAUGE, "end_timestamp": EPOCH + 604800},
            "addresses": [USER],
            "remaining_periods": 0,
        },
        {
            "campaign": {"gauge": other_gauge, "end_timestamp": EPOCH},
            "addresses": [],
            "remaining_periods": 3,
        },
    ]

    async def get_campaigns(chain_id, platform):
        return Result.ok(campaigns)

    monkeypatch.setattr(
        comparison_script.vm,
        "campaign_service",
        SimpleNamespace(get_campaigns=get_campaigns),
    )
    monkeypatch.setattr(
        comparison_script.registry,
        "get_platform",
        lambda *args: "0x" + "33" * 20,
    )
    assert await comparison_script.select_gauges("curve", 42161, EPOCH, 3) == [
        (GAUGE, [USER])
    ]


@pytest.mark.asyncio
async def test_comparison_main_forwards_explicit_epoch(
    comparison_script, monkeypatch
):
    received = []

    async def select_gauges(protocol, chain_id, epoch, max_gauges):
        received.append((protocol, chain_id, epoch, max_gauges))
        return []

    monkeypatch.setattr(comparison_script, "select_gauges", select_gauges)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare_bulk_proofs.py",
            "--protocol",
            "curve",
            "--epoch",
            str(EPOCH + 60),
            "--block",
            str(BLOCK),
            "--max-gauges",
            "2",
        ],
    )
    with pytest.raises(SystemExit, match="No active campaign found"):
        await comparison_script.main()
    assert received == [("curve", 42161, EPOCH, 2)]


@pytest.mark.parametrize(
    "failure", [None, "missing_root", "missing_point", "point_builder"]
)
@pytest.mark.parametrize("existing_output", [False, True])
def test_export_requires_complete_account_and_point_batches(
    monkeypatch, tmp_path, failure, existing_output
):
    exporter = load_script("export_batch_bags")
    monkeypatch.setattr(
        "votemarket_toolkit.shared.registry.get_gauge_controller",
        lambda protocol: CONTROLLER,
    )

    class Provider(RecordedCurveProvider):
        proof_calls = 0

        def make_request(self, method, params):
            response = super().make_request(method, params)
            if method == "eth_getProof":
                self.proof_calls += 1
                if failure == "missing_root" and self.proof_calls == 1:
                    response["result"].pop("storageHash")
                if failure == "missing_point":
                    response["result"]["storageProof"] = [
                        entry
                        for entry in response["result"]["storageProof"]
                        if int(entry["key"], 16) != int(POINT_SLOT, 16)
                    ]
            return response

    monkeypatch.setattr(
        "votemarket_toolkit.shared.retry.time.sleep", lambda seconds: None
    )
    if failure == "point_builder":
        chunk = batch_artifacts.chunk_by_calldata_size

        def refuse_point_chunk(members, stacks, budget, head):
            if head == POINT_CALL_HEAD_BYTES:
                raise ValueError("Point chunk construction failed")
            return chunk(members, stacks, budget, head)

        monkeypatch.setattr(
            batch_artifacts, "chunk_by_calldata_size", refuse_point_chunk
        )

    provider = Provider()
    manager = provider.manager()
    generate = manager.get_proofs_bulk
    results = []

    def get_proofs_bulk(**kwargs):
        # Keep point and user requests in separate RPC calls.
        result = generate(keys_per_call=3, **kwargs)
        results.append(result)
        return result

    manager.get_proofs_bulk = get_proofs_bulk
    monkeypatch.setattr(exporter, "VoteMarketProofs", lambda chain_id: manager)
    users = tmp_path / "users.txt"
    users.write_text(USER + "\n")
    target = tmp_path / "bags.json"
    previous = '{"previous_export": true}\n'
    if existing_output:
        target.write_text(previous)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_batch_bags.py",
            "--protocol",
            "curve",
            "--gauge",
            GAUGE,
            "--users",
            str(users),
            "--epoch",
            str(EPOCH),
            "--block",
            str(BLOCK),
            "--out",
            str(target),
        ],
    )
    assert exporter.main() == (1 if failure else 0)
    assert results[0].success
    assert results[0].partial is (failure == "missing_point")
    assert results[0].data.storage_root == provider.storage_root
    assert results[0].data.saw_missing_storage_root is (
        failure == "missing_root"
    )
    if failure:
        if existing_output:
            assert target.read_text() == previous
        else:
            assert not target.exists()
        assert not any(
            method == "eth_getStorageAt" for method, _ in provider.calls
        )
    else:
        output = json.loads(target.read_text())
        assert output["batch"]["chunks"][0]["accounts"] == [USER]
        assert output["batch_points"]["chunks"][0]["gauges"] == [GAUGE]


@pytest.mark.parametrize(
    "protocol,expected_mode",
    [
        ("curve", "bulk"),
        (" CURVE ", "bulk"),
        ("fxn", "bulk"),
        ("FXN", "bulk"),
        ("balancer", "bulk"),
        ("yb", "individual"),
        ("pendle", "individual"),
        ("frax", "individual"),
    ],
)
@pytest.mark.asyncio
async def test_active_proof_routing_is_automatic(
    active_script, monkeypatch, protocol, expected_mode
):
    calls = []

    async def bulk_gauge(*args):
        calls.append("bulk_gauge")
        return {"point_data_proof": "0x12", "users": {}}, {"users": {}}

    def bulk_listed(*args):
        calls.append("bulk_listed")
        return {USER: {"storage_proof": "0x34"}}

    def individual_gauge(**kwargs):
        calls.append("individual_gauge")
        return Result.ok({"point_data_proof": b"\x12"})

    def individual_user(**kwargs):
        calls.append("individual_user")
        return Result.ok({"storage_proof": b"\x34"})

    async def votes(*args):
        return SimpleNamespace(votes=[])

    async def eligible(*args):
        return Result.ok([])

    monkeypatch.setattr(active_script, "_process_gauge_bulk", bulk_gauge)
    monkeypatch.setattr(
        active_script, "_process_listed_users_bulk", bulk_listed
    )
    monkeypatch.setattr(
        active_script,
        "vm_proofs",
        SimpleNamespace(
            get_gauge_proof=individual_gauge, get_user_proof=individual_user
        ),
    )
    monkeypatch.setattr(
        active_script, "votes_service", SimpleNamespace(get_gauge_votes=votes)
    )
    monkeypatch.setattr(
        active_script,
        "vm_eligibility",
        SimpleNamespace(get_eligible_users=eligible),
    )
    proof, _ = await active_script.process_gauge(
        protocol, GAUGE, EPOCH, BLOCK, {}
    )
    listed = active_script.process_listed_users(protocol, GAUGE, BLOCK, [USER])
    assert proof["point_data_proof"] == "0x12"
    assert listed[USER]["storage_proof"] == "0x34"
    assert calls == (
        ["bulk_gauge", "bulk_listed"]
        if expected_mode == "bulk"
        else ["individual_gauge", "individual_user"]
    )


@pytest.mark.parametrize(
    "case",
    [
        "complete",
        "point_only",
        "listed_only",
        "partial_points",
        "no_gauges",
        "unsupported",
        "no_block",
        "budget",
        "missing_point",
        "missing_account",
        "missing_root",
        "conflicting_roots",
        "header_mismatch",
    ],
)
def test_active_publication_requires_complete_batches(
    active_script, monkeypatch, case
):
    monkeypatch.setattr(
        "votemarket_toolkit.shared.registry.get_gauge_controller",
        lambda protocol: CONTROLLER,
    )
    data = (
        RecordedCurveProvider()
        .manager()
        .get_proofs_bulk(
            "curve",
            BLOCK,
            gauge_epochs=[(GAUGE, EPOCH)],
            users=[(GAUGE, USER)],
        )
        .unwrap()
    )
    stacks = batch_artifacts.BatchStacks()
    stacks.record(
        BLOCK,
        data.user_nodes,
        data.gauge_nodes,
        data.storage_root,
        saw_missing_root=case == "missing_root",
    )
    platform = {
        "block_data": {"block_number": BLOCK},
        "gauges": {GAUGE: {"users": {USER: {}}, "listed_users": {}}},
    }
    if case == "point_only":
        platform["gauges"][GAUGE]["users"] = {}
    elif case == "listed_only":
        platform["gauges"][GAUGE]["listed_users"] = {"campaign": {USER: {}}}
        platform["gauges"][GAUGE]["users"] = {}
    elif case == "partial_points":
        platform["gauges"]["0x" + "22" * 20] = {"users": {}}
    elif case == "no_gauges":
        platform = {"gauges": {}}
    elif case == "no_block":
        platform["block_data"] = {}
    elif case == "missing_point":
        stacks.point_stacks.clear()
    elif case == "missing_account":
        stacks.user_stacks.clear()
    elif case == "conflicting_roots":
        stacks.record(BLOCK, {}, {}, b"\xab" * 32)
    monkeypatch.setattr(active_script, "batch_stacks", stacks)
    monkeypatch.setattr(
        active_script, "BATCH_MAX_BYTES", 1 if case == "budget" else None
    )
    protocol = "yb" if case == "unsupported" else "curve"
    header = BLOCK + 1 if case == "header_mismatch" else BLOCK
    if case in (
        "complete",
        "point_only",
        "listed_only",
        "no_gauges",
        "unsupported",
    ):
        active_script._publish_batch_artifacts(
            protocol, "42161", "platform", platform, header
        )
        assert ("batch_points" in platform) is (
            case in ("complete", "point_only", "listed_only")
        )
        if case == "point_only":
            assert "batch" not in platform["gauges"][GAUGE]
        elif case in ("complete", "listed_only"):
            assert platform["gauges"][GAUGE]["batch"]["chunks"][0][
                "accounts"
            ] == [USER]
    else:
        expected_error = (
            "Missing batch block"
            if case == "no_block"
            else "Incomplete batch artifacts"
        )
        with pytest.raises(RuntimeError, match=expected_error):
            active_script._publish_batch_artifacts(
                protocol, "42161", "platform", platform, header
            )


@pytest.mark.asyncio
async def test_comparison_keeps_distinct_modes_with_real_proofs(
    comparison_script, monkeypatch
):
    vm = comparison_script.vm
    monkeypatch.setattr(
        "votemarket_toolkit.shared.registry.get_gauge_controller",
        lambda protocol: CONTROLLER,
    )
    manager = RecordedCurveProvider().manager()
    generate = manager.get_proofs_bulk
    bulk_calls = []

    def bulk(**kwargs):
        bulk_calls.append(kwargs)
        return generate(**kwargs)

    async def votes(*args):
        return SimpleNamespace(votes=[])

    async def eligible(*args):
        return Result.ok(
            [{"user": USER, "last_vote": 0, "slope": 0, "power": 0, "end": 0}]
        )

    monkeypatch.setattr(manager, "get_proofs_bulk", bulk)
    monkeypatch.setattr(vm, "vm_proofs", manager)
    monkeypatch.setattr(
        vm, "votes_service", SimpleNamespace(get_gauge_votes=votes)
    )
    monkeypatch.setattr(
        vm, "vm_eligibility", SimpleNamespace(get_eligible_users=eligible)
    )
    original_mode = vm._uses_bulk_proofs
    individual = await comparison_script.run_mode(
        False, "curve", [(GAUGE, [USER])], EPOCH, BLOCK, {}
    )
    assert bulk_calls == []
    assert vm._uses_bulk_proofs is original_mode
    grouped = await comparison_script.run_mode(
        True, "curve", [(GAUGE, [USER])], EPOCH, BLOCK, {}
    )
    assert len(bulk_calls) == 2
    assert individual["output"] == grouped["output"]
    assert vm._uses_bulk_proofs is original_mode
    assert vm._uses_bulk_proofs("curve")
    assert not vm._uses_bulk_proofs("yb")


@pytest.mark.parametrize("bulk", [False, True])
@pytest.mark.asyncio
async def test_comparison_restores_automatic_mode_after_error(
    comparison_script, monkeypatch, bulk
):
    vm = comparison_script.vm
    original_mode = vm._uses_bulk_proofs

    async def fail(*args):
        assert vm._uses_bulk_proofs("curve") is bulk
        raise RuntimeError("Proof comparison failed")

    monkeypatch.setattr(vm, "process_gauge", fail)
    with pytest.raises(RuntimeError, match="Proof comparison failed"):
        await comparison_script.run_mode(
            bulk, "curve", [(GAUGE, [])], EPOCH, BLOCK, {}
        )
    assert vm._uses_bulk_proofs is original_mode
