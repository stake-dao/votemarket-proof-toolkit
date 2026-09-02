"""
Batch-verifier artifacts published next to the legacy proofs.

``vm_active_proofs.py`` generates, per gauge, one legacy proof blob per user
and one point proof. In bulk mode the same ``eth_getProof`` responses also
yield the raw trie nodes; this module turns them into the node bags the
``BatchVerifier`` consumes, cut by the target chain's calldata budget:

- per gauge, ``batch.chunks[]`` — ordered accounts and one minimal bag each,
  for ``setAccountDataBatch(gauge, epoch, accounts, node_bag)``;
- per platform, ``batch_points.chunks[]`` — gauges and one bag each, for
  ``setPointDataBatch(gauges, epoch, node_bag)``.

Coverage is all-or-nothing per gauge: a ``batch`` artifact always covers
every account published in the legacy fields of that gauge, otherwise it is
omitted and the consumer falls back to the legacy blobs. Point artifacts list
the gauges they do not cover. Only protocols the batch verifier supports get
artifacts, and only for a platform whose anchored block is the one the
published header / controller account proof belongs to (the verifier
registers its storage root from that header).

The legacy fields are untouched: ``safe_attach_batch_artifacts`` works on
private copies of the gauge entries (the script shares cached gauge objects
between platforms) and can never abort the legacy publication.

Stacks are keyed by block: one collector serves one protocol (one gauge
controller), whose platforms may anchor different blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from votemarket_toolkit.proofs.generators.node_bag import (
    ACCOUNT_CALL_HEAD_BYTES,
    POINT_CALL_HEAD_BYTES,
    batch_artifact,
    calldata_max_bytes,
    chunk_by_calldata_size,
    supports_batch_verifier,
)
from votemarket_toolkit.shared.logging import get_logger
from votemarket_toolkit.shared.redact import format_exception_safe

_logger = get_logger(__name__)


@dataclass
class BatchStacks:
    """Raw trie nodes of one protocol, collected while generating legacy proofs in bulk.

    Keys use lowercase addresses and include the block the proofs were
    generated at. ``storage_roots`` pins the controller storage root per
    block; a block whose responses disagreed is listed in
    ``conflicting_blocks`` and a block where at least one accepted response
    carried no root in ``blocks_without_root`` — neither gets artifacts
    (fail closed).
    """

    user_stacks: Dict[Tuple[int, str, str], List[List[bytes]]] = field(
        default_factory=dict
    )
    point_stacks: Dict[Tuple[int, str], List[bytes]] = field(
        default_factory=dict
    )
    storage_roots: Dict[int, bytes] = field(default_factory=dict)
    conflicting_blocks: Set[int] = field(default_factory=set)
    blocks_without_root: Set[int] = field(default_factory=set)

    def record(
        self,
        block_number: int,
        user_nodes: Dict[Tuple[str, str], List[List[bytes]]],
        gauge_nodes: Dict[Tuple[str, int], List[bytes]],
        storage_root: Optional[bytes],
        saw_missing_root: bool = False,
    ) -> None:
        """Keep the stacks of one bulk run (``BulkProofs`` fields)."""
        for (gauge, user), stacks in user_nodes.items():
            self.user_stacks[(block_number, gauge.lower(), user.lower())] = (
                stacks
            )
        for (gauge, _epoch), stack in gauge_nodes.items():
            self.point_stacks[(block_number, gauge.lower())] = stack
        if storage_root is None or saw_missing_root:
            self.blocks_without_root.add(block_number)
        if storage_root is None:
            return
        pinned = self.storage_roots.setdefault(block_number, storage_root)
        if pinned != storage_root:
            self.conflicting_blocks.add(block_number)
            _logger.error(
                "Controller storage root differs between bulk runs at "
                "block %d; no batch artifacts will be published for it",
                block_number,
            )


@dataclass
class BatchSummary:
    """What ``attach_batch_artifacts`` produced for one platform."""

    gauges: int = 0
    account_chunks: int = 0
    account_calldata_bytes: int = 0
    point_chunks: int = 0
    point_calldata_bytes: int = 0
    skipped: List[str] = field(default_factory=list)


def gauge_accounts(gauge_data: Dict[str, Any]) -> List[str]:
    """Every account published for a gauge (eligible and listed users).

    Sorted lowercase addresses: the chunking is greedy in this order, so the
    published chunks are canonical across runs whatever order the eligibility
    or campaign queries returned.
    """
    accounts = {user.lower() for user in gauge_data.get("users", {})}
    for campaign_users in (gauge_data.get("listed_users") or {}).values():
        accounts.update(user.lower() for user in (campaign_users or {}))
    return sorted(accounts)


def strip_batch_artifacts(platform_entry: Dict[str, Any]) -> None:
    """Remove every batch artifact from a platform entry (legacy fields kept)."""
    platform_entry.pop("batch_points", None)
    for gauge_data in platform_entry.get("gauges", {}).values():
        if isinstance(gauge_data, dict):
            gauge_data.pop("batch", None)


def attach_batch_artifacts(
    platform_entry: Dict[str, Any],
    protocol: str,
    chain_id: Any,
    block_number: int,
    stacks: BatchStacks,
    max_bytes: Optional[int] = None,
) -> BatchSummary:
    """Add ``batch`` to the gauges of ``platform_entry`` and ``batch_points`` to it.

    Any artifact already present is removed first, so the entry ends up with
    exactly the artifacts of ``block_number`` or none. A gauge gets a
    ``batch`` only when every one of its published accounts has trie nodes
    at that block and fits the budget; otherwise it is left without one and
    the reason is in the summary. Point artifacts cover the gauges with nodes
    and name the others in ``missing_gauges``.
    """
    summary = BatchSummary()
    strip_batch_artifacts(platform_entry)
    if not supports_batch_verifier(protocol):
        summary.skipped.append(
            f"protocol {protocol} is not supported by the batch verifier"
        )
        return summary
    if block_number in stacks.conflicting_blocks:
        summary.skipped.append(
            f"conflicting storage roots at block {block_number}"
        )
        return summary
    if block_number in stacks.blocks_without_root:
        summary.skipped.append(
            f"no storage root reported at block {block_number}"
        )
        return summary

    budget = (
        max_bytes if max_bytes is not None else calldata_max_bytes(chain_id)
    )
    storage_root = stacks.storage_roots.get(block_number)

    point_stacks: Dict[str, List[List[bytes]]] = {}
    missing_gauges: List[str] = []
    for gauge, gauge_data in platform_entry.get("gauges", {}).items():
        gauge_key = gauge.lower()
        accounts = gauge_accounts(gauge_data)
        account_stacks = {
            account: stacks.user_stacks[(block_number, gauge_key, account)]
            for account in accounts
            if (block_number, gauge_key, account) in stacks.user_stacks
        }
        missing = len(accounts) - len(account_stacks)
        if missing:
            # All-or-nothing: a partial batch would hide legacy accounts.
            summary.skipped.append(
                f"gauge {gauge}: {missing}/{len(accounts)} account(s) "
                f"without trie nodes at block {block_number}, no batch"
            )
        elif accounts:
            try:
                chunks = chunk_by_calldata_size(
                    accounts, account_stacks, budget, ACCOUNT_CALL_HEAD_BYTES
                )
            except ValueError as exc:
                summary.skipped.append(f"gauge {gauge}: {exc}")
            else:
                gauge_data["batch"] = batch_artifact(
                    chunks,
                    "accounts",
                    storage_root,
                    block_number=block_number,
                    accounts_total=len(accounts),
                )
                summary.gauges += 1
                summary.account_chunks += len(chunks)
                summary.account_calldata_bytes += sum(
                    c.calldata_bytes for c in chunks
                )

        if (block_number, gauge_key) in stacks.point_stacks:
            point_stacks[gauge_key] = [
                stacks.point_stacks[(block_number, gauge_key)]
            ]
        else:
            missing_gauges.append(gauge_key)

    if point_stacks:
        # Sorted gauges: canonical point chunks across runs.
        point_members = sorted(point_stacks)
        try:
            chunks = chunk_by_calldata_size(
                point_members, point_stacks, budget, POINT_CALL_HEAD_BYTES
            )
        except ValueError as exc:
            summary.skipped.append(f"points: {exc}")
        else:
            platform_entry["batch_points"] = batch_artifact(
                chunks,
                "gauges",
                storage_root,
                block_number=block_number,
                missing_gauges=sorted(missing_gauges),
            )
            summary.point_chunks = len(chunks)
            summary.point_calldata_bytes = sum(
                c.calldata_bytes for c in chunks
            )
    return summary


def safe_attach_batch_artifacts(
    platform_entry: Dict[str, Any],
    protocol: str,
    chain_id: Any,
    block_number: Any,
    stacks: BatchStacks,
    max_bytes: Optional[int] = None,
    header_block: Any = None,
) -> BatchSummary:
    """``attach_batch_artifacts`` that can never break legacy publication.

    The gauge entries are replaced by private shallow copies first: the
    script shares cached gauge objects between platforms, and each platform
    must carry the artifacts of its own block only. When ``header_block`` is
    given, a platform anchored on another block gets no artifacts: the
    published header / controller account proof would not let the verifier
    register the matching storage root. Any failure is logged (redacted),
    every artifact is removed and the legacy fields are left untouched.
    """
    try:
        platform_entry["gauges"] = {
            gauge: dict(gauge_data)
            for gauge, gauge_data in platform_entry.get("gauges", {}).items()
        }
        block = int(block_number)
        if header_block is not None and int(header_block) != block:
            strip_batch_artifacts(platform_entry)
            summary = BatchSummary()
            summary.skipped.append(
                f"platform anchored at block {block} but the published "
                f"header is for block {int(header_block)}, no batch artifacts"
            )
            return summary
        return attach_batch_artifacts(
            platform_entry, protocol, chain_id, block, stacks, max_bytes
        )
    except Exception as exc:  # noqa: BLE001 - artifacts are best-effort
        _logger.error(
            "Batch artifacts failed for protocol %s on chain %s: %s",
            protocol,
            chain_id,
            format_exception_safe(exc),
        )
        strip_batch_artifacts(platform_entry)
        summary = BatchSummary()
        summary.skipped.append(
            f"internal error, legacy proofs only: {format_exception_safe(exc)}"
        )
        return summary
