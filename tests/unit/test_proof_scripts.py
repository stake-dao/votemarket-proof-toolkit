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
