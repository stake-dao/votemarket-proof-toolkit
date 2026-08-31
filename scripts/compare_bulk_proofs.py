#!/usr/bin/env python3
"""
Compare the per-request and bulk proof paths of vm_active_proofs.py.

Runs process_gauge() + process_listed_users() twice on the same gauges and
block (BULK_PROOFS=False, then True), then compares the produced structures
byte for byte and reports RPC call counts and wall time for each mode.

Usage:
    uv run scripts/compare_bulk_proofs.py [--protocol curve] [--chain-id 42161]
        [--block N] [--epoch TS] [--max-gauges 3] [--keys-per-call 100]

By default the block is the canonical block stored by the platform oracle
for the current epoch (same as vm_all_platforms.py). Requires the RPC
environment variables used by the pipeline. Exits with status 1 when the
two modes disagree.

Note on timings: connections and the votes cache are warmed up before the
first run, but wall-clock times remain indicative — the authoritative
outputs are the byte comparison and the RPC call counts.
"""

import argparse
import asyncio
import collections
import json
import os
import sys
import time
from typing import Any, Dict, Iterator, List, Tuple

from dotenv import load_dotenv
from rich.console import Console
from web3.middleware import Web3Middleware

load_dotenv()

import vm_active_proofs as vm  # noqa: E402  (sibling script)

from votemarket_toolkit.shared import registry  # noqa: E402
from votemarket_toolkit.shared.services.web3_service import (  # noqa: E402
    Web3Service,
)
from votemarket_toolkit.utils import get_rounded_epoch  # noqa: E402

console = Console()
OUTPUT_DIR = "temp"


def instrument(w3, counter: collections.Counter) -> None:
    """Count JSON-RPC methods issued through a Web3 instance.

    Uses a web3 middleware rather than patching ``provider.make_request``:
    web3 caches the middleware/request chain after the first request, so a
    patched ``make_request`` would be ignored once any call has been made.
    """

    class CountingMiddleware(Web3Middleware):
        def wrap_make_request(self, make_request):
            def middleware(method, params):
                counter[method] += 1
                return make_request(method, params)

            return middleware

    w3.middleware_onion.add(
        CountingMiddleware, name=f"rpc_counter_{id(counter)}"
    )


def oracle_block(protocol: str, chain_id: int, epoch: int) -> int:
    """Canonical block for ``epoch`` from the platform oracle (v2)."""
    platform = registry.get_platform(protocol, chain_id, "v2")
    if not platform:
        raise SystemExit(f"No v2 platform for {protocol} on chain {chain_id}")
    web3_service = Web3Service.get_instance(chain_id)
    platform_contract = web3_service.get_contract(platform, "vm_platform")
    lens = web3_service.get_contract(
        platform_contract.functions.ORACLE().call(), "oracle_lens"
    )
    oracle = web3_service.get_contract(
        lens.functions.oracle().call(), "oracle"
    )
    block = oracle.functions.epochBlockNumber(epoch).call()[2]
    if block == 0:
        raise SystemExit(f"Oracle has no block for epoch {epoch}")
    return block


async def select_gauges(
    protocol: str, chain_id: int, max_gauges: int
) -> List[Tuple[str, List[str]]]:
    """Gauges of active campaigns, listed-user campaigns first."""
    platform = registry.get_platform(protocol, chain_id, "v2")
    result = await vm.campaign_service.get_campaigns(chain_id, platform)
    if not result.success:
        raise SystemExit(f"Campaign fetch failed: {result.errors[0].message}")
    active = [c for c in result.data if vm.is_campaign_active(c)]
    active.sort(key=lambda c: -len(c.get("addresses", [])))

    selected: List[Tuple[str, List[str]]] = []
    seen = set()
    for campaign in active:
        gauge = campaign["campaign"]["gauge"].lower()
        if gauge in seen:
            continue
        seen.add(gauge)
        selected.append((gauge, list(campaign.get("addresses", []))[:5]))
        if len(selected) >= max_gauges:
            break
    return selected


def diff_paths(a: Any, b: Any, path: str = "") -> Iterator[str]:
    """Yield the paths where two JSON-like structures differ."""
    if type(a) is not type(b):
        yield f"{path}: type {type(a).__name__} != {type(b).__name__}"
        return
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                side = "bulk only" if key not in a else "per-request only"
                yield f"{path}/{key}: {side}"
            else:
                yield from diff_paths(a[key], b[key], f"{path}/{key}")
    elif isinstance(a, list):
        if len(a) != len(b):
            yield f"{path}: len {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diff_paths(x, y, f"{path}[{i}]")
    elif a != b:
        yield f"{path}: {str(a)[:40]} != {str(b)[:40]}"


async def run_mode(
    bulk: bool,
    protocol: str,
    gauges: List[Tuple[str, List[str]]],
    epoch: int,
    block: int,
    counters: Dict[str, collections.Counter],
) -> Dict[str, Any]:
    vm.BULK_PROOFS = bulk
    for counter in counters.values():
        counter.clear()
    user_proofs_cache: Dict[str, Any] = {}
    output: Dict[str, Any] = {}
    started = time.time()
    for gauge, listed_users in gauges:
        proof_data, vote_data = await vm.process_gauge(
            protocol, gauge, epoch, block, user_proofs_cache
        )
        listed_data = vm.process_listed_users(
            protocol, gauge, block, listed_users
        )
        output[gauge] = {
            "proof": proof_data,
            "votes": vote_data,
            "listed": listed_data,
        }
    return {
        "output": output,
        "seconds": time.time() - started,
        "rpc": {name: dict(counter) for name, counter in counters.items()},
    }


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare per-request vs bulk proof generation"
    )
    parser.add_argument("--protocol", default="curve")
    parser.add_argument("--chain-id", type=int, default=42161)
    parser.add_argument("--block", type=int, default=None)
    parser.add_argument("--epoch", type=int, default=None)
    parser.add_argument("--max-gauges", type=int, default=3)
    parser.add_argument("--keys-per-call", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.max_gauges < 1:
        parser.error("--max-gauges must be >= 1")
    if args.keys_per_call is not None and args.keys_per_call < 1:
        parser.error("--keys-per-call must be >= 1")

    if not args.verbose:
        vm.console = Console(quiet=True)
    if args.keys_per_call is not None:
        vm.BULK_KEYS_PER_CALL = args.keys_per_call

    epoch = get_rounded_epoch(args.epoch or int(time.time()))
    block = args.block or oracle_block(args.protocol, args.chain_id, epoch)
    gauges = await select_gauges(args.protocol, args.chain_id, args.max_gauges)
    if not gauges:
        raise SystemExit("No active campaign found")

    console.print(
        f"protocol={args.protocol} chain={args.chain_id} epoch={epoch} "
        f"block={block} keys_per_call={vm.BULK_KEYS_PER_CALL}"
    )
    console.print(
        "gauges: "
        + ", ".join(
            f"{gauge[:10]}({len(listed)} listed)" for gauge, listed in gauges
        )
    )

    counters = {
        "proofs": collections.Counter(),
        "eligibility": collections.Counter(),
    }
    instrument(vm.vm_proofs.web3_service.w3, counters["proofs"])
    instrument(vm.vm_eligibility.web3_service.w3, counters["eligibility"])

    # Warm up HTTP connections and the votes cache so the first timed mode
    # does not pay one-off costs the second mode skips.
    vm.vm_proofs.web3_service.w3.eth.block_number
    vm.vm_eligibility.web3_service.w3.eth.block_number
    await vm.votes_service.get_gauge_votes(args.protocol, gauges[0][0], block)

    runs = {}
    for bulk in (False, True):
        runs[bulk] = await run_mode(
            bulk, args.protocol, gauges, epoch, block, counters
        )
        output = runs[bulk]["output"]
        users = sum(len(o["proof"]["users"]) for o in output.values())
        listed = sum(len(o["listed"]) for o in output.values())
        mode = "bulk" if bulk else "per-request"
        get_proof_calls = runs[bulk]["rpc"]["proofs"].get("eth_getProof", 0)
        console.print(
            f"{mode:12s}: {users} user proofs + {listed} listed proofs in "
            f"{runs[bulk]['seconds']:.1f}s | eth_getProof calls: "
            f"{get_proof_calls}"
        )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for bulk, name in ((False, "per_request"), (True, "bulk")):
        path = os.path.join(OUTPUT_DIR, f"compare_bulk_proofs_{name}.json")
        with open(path, "w") as f:
            json.dump(runs[bulk]["output"], f, indent=1)

    differences = list(diff_paths(runs[False]["output"], runs[True]["output"]))
    if differences:
        console.print(
            f"[bold red]RESULT: {len(differences)} difference(s)[/bold red]"
        )
        for line in differences[:20]:
            console.print(f"  {line}")
        return 1

    total = sum(
        1 + len(o["proof"]["users"]) + len(o["listed"])
        for o in runs[False]["output"].values()
    )
    console.print(
        f"[bold green]RESULT: IDENTICAL[/bold green] — {total} proof blobs and "
        f"vote data match exactly (files in {OUTPUT_DIR}/)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
