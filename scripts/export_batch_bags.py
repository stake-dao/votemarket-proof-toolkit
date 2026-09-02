#!/usr/bin/env python3
"""
Export real node bags for an end-to-end check against the Solidity library.

Builds, from a live ``eth_getProof`` at a recent block, the batch-verifier
artifacts of one gauge exactly like ``vm_active_proofs.py --bulk-proofs``
does, together with the slot values read back with ``eth_getStorageAt``, so a
Foundry test can feed the bags to ``MerklePatriciaBatchVerifier`` and compare
the returned values (see docs/batch-verifier-rollout.md).

Usage:
    uv run scripts/export_batch_bags.py --protocol curve --gauge 0x... \\
        --users users.txt --epoch 1787788800 --chain-id 42161 --out bags.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from web3 import Web3

from votemarket_toolkit.proofs.batch_artifacts import (
    BatchStacks,
    attach_batch_artifacts,
)
from votemarket_toolkit.proofs.generators.bulk_proof import (
    get_gauge_proof_slots,
    get_user_proof_slots,
)
from votemarket_toolkit.proofs.manager import VoteMarketProofs
from votemarket_toolkit.shared import registry
from votemarket_toolkit.utils import get_rounded_epoch


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--gauge", required=True)
    parser.add_argument(
        "--users", required=True, help="File with one account per line"
    )
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--chain-id", type=int, default=42161)
    parser.add_argument(
        "--block", type=int, default=None, help="Default: head - 20"
    )
    parser.add_argument("--batch-max-bytes", type=int, default=None)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = _parse_args()
    users = [
        line.strip().lower()
        for line in Path(args.users).read_text().splitlines()
        if line.strip()
    ]
    gauge = args.gauge.lower()
    epoch = get_rounded_epoch(args.epoch)

    proofs = VoteMarketProofs(chain_id=1)
    w3 = proofs.web3_service.w3
    block = args.block or w3.eth.block_number - 20

    result = proofs.get_proofs_bulk(
        protocol=args.protocol,
        block_number=block,
        gauge_epochs=[(gauge, epoch)],
        users=[(gauge, user) for user in users],
    )
    if not result.success:
        # Redacted messages only: the errors keep the raw exceptions, which
        # may embed the provider URL.
        for error in result.errors:
            print(f"bulk generation failed: {error.message}", file=sys.stderr)
        return 1
    data = result.data

    stacks = BatchStacks()
    stacks.record(block, data.user_nodes, data.gauge_nodes, data.storage_root)
    platform: Dict[str, Any] = {
        "block_data": {"block_number": block},
        "gauges": {
            gauge: {
                "point_data_proof": "0x",
                "users": {user: {"storage_proof": "0x"} for user in users},
                "listed_users": {},
            }
        },
    }
    summary = attach_batch_artifacts(
        platform,
        args.protocol,
        args.chain_id,
        block,
        stacks,
        max_bytes=args.batch_max_bytes,
    )
    if "batch" not in platform["gauges"][gauge]:
        print(f"no batch artifact: {summary.skipped}", file=sys.stderr)
        return 1

    controller = Web3.to_checksum_address(
        registry.get_gauge_controller(args.protocol)
    )

    def _value(slot_hex: str) -> str:
        raw = w3.eth.get_storage_at(controller, int(slot_hex, 16), block)
        return str(int.from_bytes(raw, "big"))

    expected: Dict[str, Dict[str, str]] = {}
    for user in users:
        slots: List[str] = get_user_proof_slots(args.protocol, gauge, user)
        values = [_value(slot) for slot in slots]
        expected[user] = {
            "last_vote": values[0],
            "slope": values[1],
            "end": values[2],
        }
    point_slot = get_gauge_proof_slots(args.protocol, gauge, epoch)[0]

    args.out.write_text(
        json.dumps(
            {
                "protocol": args.protocol,
                "chain_id": args.chain_id,
                "block_number": block,
                "epoch": epoch,
                "gauge": gauge,
                "observed_storage_root": (
                    "0x" + data.storage_root.hex()
                    if data.storage_root
                    else None
                ),
                "batch": platform["gauges"][gauge]["batch"],
                "batch_points": platform.get("batch_points"),
                "expected": expected,
                "expected_bias": _value(point_slot),
            }
        )
    )
    chunks = platform["gauges"][gauge]["batch"]["chunks"]
    print(
        f"wrote {args.out} ({args.out.stat().st_size:,} bytes): "
        f"{len(chunks)} account chunk(s) "
        f"{[(len(c['accounts']), c['calldata_bytes']) for c in chunks]}, "
        f"{summary.point_chunks} point chunk(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
