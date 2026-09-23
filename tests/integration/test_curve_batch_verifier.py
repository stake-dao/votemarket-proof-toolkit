"""Recorded proofs -> real Python exporter -> unmodified Solidity verifier.

The dedicated CI job requires this test. Locally, provide
VOTEMARKET_CONTRACTS_PATH and install Forge; no RPC or credentials are used.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from eth_abi import encode

from tests.curve_fixture import (
    BLOCK,
    CONTROLLER,
    EPOCH,
    EXPECTED,
    GAUGE,
    POINT_SLOT,
    SPELLINGS,
    USER,
    USER_SLOTS,
    RecordedCurveProvider,
    storage_path,
)

CONTRACT_FILES = (
    "verifiers/BatchVerifier.sol",
    "oracle/Oracle.sol",
    "interfaces/IOracle.sol",
    "utils/RLPReader.sol",
    "utils/StateProofVerifier.sol",
    "utils/MerklePatriciaProofVerifier.sol",
    "utils/MerklePatriciaBatchVerifier.sol",
)


@pytest.mark.integration
def test_curve_spellings_write_recorded_values_in_solidity(
    tmp_path, monkeypatch
):
    contracts = os.getenv("VOTEMARKET_CONTRACTS_PATH")
    forge = shutil.which("forge")
    if not contracts or not forge:
        if os.getenv("REQUIRE_BATCH_VERIFIER_TEST") == "1":
            pytest.fail("VOTEMARKET_CONTRACTS_PATH and Forge are required")
        pytest.skip("Set VOTEMARKET_CONTRACTS_PATH and install Forge")
    source = Path(contracts).resolve() / "packages/votemarket/src"
    project = tmp_path / "solidity"
    project.mkdir()
    for name in CONTRACT_FILES:
        target = project / "src" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    tests = Path(__file__).resolve().parents[1]
    (project / "test").mkdir()
    shutil.copyfile(
        tests / "solidity/CurveProtocol.t.sol",
        project / "test/CurveProtocol.t.sol",
    )
    (project / "foundry.toml").write_text(
        '[profile.default]\nsolc_version = "0.8.28"\n'
        'evm_version = "cancun"\noptimizer = true\noptimizer_runs = 200\n'
        'fs_permissions = [{ access = "read", path = "." }]\n'
    )
    script = tests.parent / "scripts/export_batch_bags.py"
    spec = importlib.util.spec_from_file_location("curve_export", script)
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    monkeypatch.setattr(exporter, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        "votemarket_toolkit.shared.registry.get_gauge_controller",
        lambda protocol: CONTROLLER,
    )
    users = tmp_path / "users.txt"
    users.write_text(USER + "\n")
    bags = []
    for index, spelling in enumerate(SPELLINGS):
        provider = RecordedCurveProvider()
        monkeypatch.setattr(
            exporter, "VoteMarketProofs", lambda chain_id: provider.manager()
        )
        target = tmp_path / f"export-{index}.json"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                str(script),
                "--protocol",
                spelling,
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
        assert exporter.main() == 0
        result = json.loads(target.read_text())
        assert result["protocol"] == "curve"
        assert result["expected"][USER] == dict(
            zip(("last_vote", "slope", "end"), map(str, EXPECTED[:3]))
        )
        assert result["expected_bias"] == str(EXPECTED[3])
        account_chunks = result["batch"]["chunks"]
        point_chunks = result["batch_points"]["chunks"]
        assert len(account_chunks) == len(point_chunks) == 1
        assert account_chunks[0]["accounts"] == [USER]
        assert point_chunks[0]["gauges"] == [GAUGE]
        account_bag = bytes.fromhex(account_chunks[0]["node_bag"][2:])
        point_bag = bytes.fromhex(point_chunks[0]["node_bag"][2:])
        bags.append((account_bag, point_bag))
        data = (
            bytes.fromhex(provider.fixture["block_header_rlp"][2:]),
            bytes.fromhex(provider.fixture["gc_proof"][2:]),
            provider.storage_root,
            GAUGE,
            USER,
            account_bag,
            point_bag,
            EXPECTED,
            [storage_path(slot) for slot in USER_SLOTS],
            storage_path(POINT_SLOT),
        )
        (project / f"curve-{index}.abi").write_bytes(
            encode(
                [
                    "(bytes,bytes,bytes32,address,address,bytes,bytes,uint256[4],bytes32[3],bytes32)"
                ],
                [data],
            )
        )
    assert all(value == bags[0] for value in bags)
    command = [forge, "test", "--root", str(project), "-vv"]
    if os.getenv("SOLC_BINARY"):
        command.extend(["--use", os.environ["SOLC_BINARY"], "--offline"])
    env = dict(os.environ, FOUNDRY_PROFILE="default")
    run = subprocess.run(
        command,
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    print(run.stdout)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "4 passed; 0 failed; 0 skipped" in run.stdout
