"""
Bulk storage-proof generation: many storage keys per ``eth_getProof`` call.

Every gauge proof and user proof for a protocol at a given block targets the
same account (the gauge controller). ``eth_getProof`` accepts a list of
storage keys for one account, so the keys of many gauges/users can be sent
in a single call and the response split back per request.

Each storage proof is the Merkle path of its own key and does not depend on
the other keys in the request, so the RLP blobs produced here are identical,
byte for byte, to the ones produced by ``generate_gauge_proof`` and
``generate_user_proof`` (see ``tests/unit/test_bulk_proofs.py``).

Failure handling: a failing chunk (timeout, provider limit, malformed
response) is split in half and retried recursively. A chunk that shrinks to
a single request is retried like a regular per-request call; if it still
fails, only that request is reported as failed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from hexbytes import HexBytes
from web3 import Web3

from votemarket_toolkit.proofs.generators.gauge_proof import (
    get_gauge_time_storage_slot,
    get_gauge_time_storage_slot_pendle,
    get_gauge_time_storage_slot_pre_vyper03,
    get_gauge_time_storage_slot_yb,
)
from votemarket_toolkit.proofs.generators.user_proof import (
    get_user_gauge_storage_slot,
    get_user_gauge_storage_slot_pendle,
    get_user_gauge_storage_slot_pre_vyper03,
)
from votemarket_toolkit.shared import registry
from votemarket_toolkit.shared.logging import get_logger
from votemarket_toolkit.shared.redact import format_exception_safe
from votemarket_toolkit.shared.retry import retry_sync_operation
from votemarket_toolkit.utils.blockchain import encode_rlp_proofs

_logger = get_logger(__name__)

# Conservative default: ~4.6 KB per key on the Curve gauge controller,
# i.e. ~475 KB per response. Measured on Alchemy (2026-08-31): hard cap of
# 1024 storage keys per eth_getProof call, billed 20 CU per call regardless
# of the number of keys, so larger chunks only trade response size/latency
# against the number of calls.
DEFAULT_KEYS_PER_CALL = 100

GAUGE = "gauge"
USER = "user"


@dataclass(frozen=True)
class ProofRequest:
    """One proof to generate (what a single eth_getProof call does today).

    Addresses are normalized to lowercase so requests can be used as
    dictionary keys regardless of the caller's casing.
    """

    kind: str
    gauge: str
    epoch: Optional[int] = None
    user: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind not in (GAUGE, USER):
            raise ValueError(f"Unknown proof request kind: {self.kind}")
        object.__setattr__(self, "gauge", self.gauge.lower())
        if self.kind == GAUGE and self.epoch is None:
            raise ValueError("Gauge proof request requires an epoch")
        if self.kind == USER:
            if self.user is None:
                raise ValueError("User proof request requires a user")
            object.__setattr__(self, "user", self.user.lower())

    @classmethod
    def for_gauge(cls, gauge: str, epoch: int) -> "ProofRequest":
        """Point-weights proof for ``gauge`` at ``epoch``."""
        return cls(kind=GAUGE, gauge=gauge, epoch=epoch)

    @classmethod
    def for_user(cls, gauge: str, user: str) -> "ProofRequest":
        """Vote proof for ``user`` on ``gauge``."""
        return cls(kind=USER, gauge=gauge, user=user)


@dataclass
class BulkProofStats:
    """Counters describing one bulk run (useful to compare RPC usage)."""

    requests: int = 0
    keys: int = 0
    rpc_calls: int = 0
    splits: int = 0
    failed_requests: int = 0
    aborted: bool = False


@dataclass
class BulkProofResult:
    """Outcome of ``generate_proofs_bulk``.

    ``proofs`` maps each request to ``(account_proof, storage_proof)``, the
    same tuple returned by the per-request generators. ``errors`` maps the
    requests that could not be generated to the last exception seen.
    """

    proofs: Dict[ProofRequest, Tuple[bytes, bytes]] = field(
        default_factory=dict
    )
    errors: Dict[ProofRequest, Exception] = field(default_factory=dict)
    stats: BulkProofStats = field(default_factory=BulkProofStats)


# ---------------------------------------------------------------------------
# Storage slot computation (mirrors generate_gauge_proof / generate_user_proof)
# ---------------------------------------------------------------------------


def get_gauge_proof_slots(
    protocol: str, gauge_address: str, current_epoch: int
) -> List[str]:
    """Storage keys requested by ``generate_gauge_proof`` (same order)."""
    gauge_slots = registry.get_gauge_slots(protocol)
    if not gauge_slots:
        raise ValueError(f"Unknown protocol: {protocol}")

    position_functions = {
        "curve": get_gauge_time_storage_slot_pre_vyper03,
        "yb": get_gauge_time_storage_slot_yb,
        "pendle": get_gauge_time_storage_slot_pendle,
    }
    get_position = position_functions.get(
        protocol, get_gauge_time_storage_slot
    )
    position = get_position(
        Web3.to_checksum_address(gauge_address.lower()),
        current_epoch,
        gauge_slots["point_weights"],
    )
    return [Web3.to_hex(position)]


def get_user_proof_slots(
    protocol: str, gauge_address: str, user: str
) -> List[str]:
    """Storage keys requested by ``generate_user_proof`` (same order)."""
    gauge_slots = registry.get_gauge_slots(protocol)
    if not gauge_slots:
        raise ValueError(f"Unknown protocol: {protocol}")

    user_cs = Web3.to_checksum_address(user.lower())
    gauge_cs = Web3.to_checksum_address(gauge_address.lower())

    slots: List[str] = []
    if protocol != "pendle":
        slots.append(
            Web3.to_hex(
                get_user_gauge_storage_slot(
                    user_cs, gauge_cs, gauge_slots["last_user_vote"]
                )
            )
        )

    base_slot = gauge_slots["vote_user_slope"]
    additional_offsets = [2]
    if protocol == "curve":
        slope_slot = get_user_gauge_storage_slot_pre_vyper03(
            user_cs, gauge_cs, base_slot
        )
    elif protocol == "yb":
        slope_slot = get_user_gauge_storage_slot(user_cs, gauge_cs, base_slot)
        additional_offsets = [1, 3]
    elif protocol == "pendle":
        slope_slot = get_user_gauge_storage_slot_pendle(
            user_cs, gauge_cs, base_slot
        )
        additional_offsets = [1]
    else:
        slope_slot = get_user_gauge_storage_slot(user_cs, gauge_cs, base_slot)

    slots.append(Web3.to_hex(slope_slot))
    slots.extend(
        Web3.to_hex(slope_slot + offset) for offset in additional_offsets
    )
    return slots


def _slots_for(protocol: str, request: ProofRequest) -> List[str]:
    if request.kind == GAUGE:
        return get_gauge_proof_slots(protocol, request.gauge, request.epoch)
    return get_user_proof_slots(protocol, request.gauge, request.user)


# ---------------------------------------------------------------------------
# Bulk generation
# ---------------------------------------------------------------------------


def generate_proofs_bulk(
    web_3: Web3,
    protocol: str,
    block_number: int,
    requests: Sequence[ProofRequest],
    keys_per_call: int = DEFAULT_KEYS_PER_CALL,
    max_retries: int = 3,
    base_delay: float = 1.0,
    abort_after_failures: int = 8,
) -> BulkProofResult:
    """
    Generate many gauge/user proofs with grouped ``eth_getProof`` calls.

    Args:
        web_3: Web3 instance connected to the chain hosting the controller.
        protocol: Protocol name (e.g. "curve", "balancer").
        block_number: Block number shared by every requested proof.
        requests: Proofs to generate (duplicates are removed).
        keys_per_call: Maximum storage keys per ``eth_getProof`` call. A
            request with more keys than this is sent alone.
        max_retries: Attempts for a chunk reduced to a single request.
        base_delay: Base delay between those attempts (seconds).
        abort_after_failures: Circuit breaker — after this many consecutive
            single-request failures (a provider-wide outage), remaining
            requests are failed without further RPC calls and
            ``stats.aborted`` is set.

    Returns:
        BulkProofResult with per-request proofs, per-request errors and
        RPC usage statistics.

    Raises:
        ValueError: Unknown protocol, missing gauge controller or invalid
            ``keys_per_call`` (configuration errors, not RPC failures).
    """
    if keys_per_call < 1:
        raise ValueError("keys_per_call must be >= 1")
    if not registry.get_gauge_slots(protocol):
        raise ValueError(f"Unknown protocol: {protocol}")

    gauge_controller = registry.get_gauge_controller(protocol)
    if not gauge_controller:
        raise ValueError(f"No gauge controller found for protocol: {protocol}")
    controller_address = Web3.to_checksum_address(gauge_controller.lower())

    unique_requests = list(dict.fromkeys(requests))
    if not unique_requests:
        return BulkProofResult()

    result = BulkProofResult()
    result.stats.requests = len(unique_requests)

    # A malformed request (bad address, missing slot) must not abort the
    # batch: record it as a per-request error and keep the valid ones.
    slots_by_request: Dict[ProofRequest, List[str]] = {}
    for request in unique_requests:
        try:
            slots_by_request[request] = _slots_for(protocol, request)
        except Exception as exc:  # noqa: BLE001 - reported per request
            _logger.error(
                "Invalid proof request (%s %s%s): %s",
                request.kind,
                request.gauge,
                f" / {request.user}" if request.user else "",
                format_exception_safe(exc),
            )
            result.errors[request] = exc
    valid_requests = [r for r in unique_requests if r in slots_by_request]
    result.stats.keys = sum(len(s) for s in slots_by_request.values())

    fetcher = _ChunkFetcher(
        web_3=web_3,
        controller_address=controller_address,
        block_number=block_number,
        slots_by_request=slots_by_request,
        result=result,
        max_retries=max_retries,
        base_delay=base_delay,
        abort_after_failures=abort_after_failures,
    )
    for chunk in _pack_requests(
        valid_requests, slots_by_request, keys_per_call
    ):
        fetcher.fetch(chunk)

    result.stats.failed_requests = len(result.errors)
    _logger.debug(
        "Bulk eth_getProof: %d call(s) for %d keys / %d proofs "
        "(%d splits, %d failed)",
        result.stats.rpc_calls,
        result.stats.keys,
        result.stats.requests,
        result.stats.splits,
        result.stats.failed_requests,
    )
    return result


def _pack_requests(
    requests: List[ProofRequest],
    slots_by_request: Dict[ProofRequest, List[str]],
    keys_per_call: int,
) -> List[List[ProofRequest]]:
    """Group whole requests into chunks of at most ``keys_per_call`` keys."""
    chunks: List[List[ProofRequest]] = []
    current: List[ProofRequest] = []
    current_keys = 0
    for request in requests:
        n_keys = len(slots_by_request[request])
        if current and current_keys + n_keys > keys_per_call:
            chunks.append(current)
            current, current_keys = [], 0
        current.append(request)
        current_keys += n_keys
    if current:
        chunks.append(current)
    return chunks


def _check_storage_key(expected_hex: str, entry: Any) -> None:
    """Fail-closed check that the node answered for the key we asked.

    EIP-1186 returns storage proofs in request order; a missing or
    mismatching key means the response cannot be trusted for splitting.
    """
    key = entry.get("key") if hasattr(entry, "get") else None
    if key is None:
        raise ValueError("eth_getProof storage proof entry has no 'key' field")
    if int.from_bytes(bytes(HexBytes(key)), "big") != int(expected_hex, 16):
        raise ValueError(
            "eth_getProof storage proof order mismatch for key "
            f"{expected_hex}"
        )


# Failure signatures that call for splitting the chunk rather than
# retrying it as-is (size caps and malformed/shifted responses).
_SPLIT_ERROR_MARKERS = (
    "too many storage keys",
    "response too large",
    "request entity too large",
    "413",
    "-32602",
    "storage proofs for",
    "order mismatch",
    "has no 'key' field",
    "exceeds",
)


def _looks_like_size_or_shape_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _SPLIT_ERROR_MARKERS)


class _ChunkFetcher:
    """Fetches chunks of requests, splitting them in half on failure."""

    def __init__(
        self,
        web_3: Web3,
        controller_address: str,
        block_number: int,
        slots_by_request: Dict[ProofRequest, List[str]],
        result: BulkProofResult,
        max_retries: int,
        base_delay: float,
        abort_after_failures: int,
    ) -> None:
        self._web_3 = web_3
        self._controller = controller_address
        self._block = block_number
        self._slots = slots_by_request
        self._result = result
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._abort_after = max(1, abort_after_failures)
        self._consecutive_failures = 0
        self._aborted = False

    def fetch(self, chunk: List[ProofRequest], retried: bool = False) -> None:
        if self._aborted:
            for request in chunk:
                self._result.errors.setdefault(
                    request,
                    RuntimeError(
                        "bulk proof generation aborted after repeated "
                        "RPC failures"
                    ),
                )
            return
        keys = [key for request in chunk for key in self._slots[request]]
        try:
            raw_proof = self._get_proof(keys, single=len(chunk) == 1)
            proofs = self._split_response(raw_proof, chunk, keys)
        except Exception as exc:  # noqa: BLE001 - handled per chunk
            self._handle_failure(chunk, exc, retried)
            return
        self._consecutive_failures = 0
        self._result.proofs.update(proofs)

    def _get_proof(self, keys: List[str], single: bool) -> Any:
        def _call() -> Any:
            self._result.stats.rpc_calls += 1
            return self._web_3.eth.get_proof(
                self._controller, keys, self._block
            )

        if not single:
            # Multi-request chunk: fail fast, the split gives a second chance
            return _call()
        return retry_sync_operation(
            _call,
            max_attempts=self._max_retries,
            base_delay=self._base_delay,
            operation_name=f"bulk_proof_{len(keys)}_keys",
        )

    def _split_response(
        self,
        raw_proof: Any,
        chunk: List[ProofRequest],
        keys: List[str],
    ) -> Dict[ProofRequest, Tuple[bytes, bytes]]:
        account_proof = raw_proof["accountProof"]
        storage_proofs = raw_proof["storageProof"]
        if len(storage_proofs) != len(keys):
            raise ValueError(
                f"eth_getProof returned {len(storage_proofs)} storage proofs "
                f"for {len(keys)} keys"
            )

        proofs: Dict[ProofRequest, Tuple[bytes, bytes]] = {}
        cursor = 0
        for request in chunk:
            request_keys = self._slots[request]
            entries = storage_proofs[cursor : cursor + len(request_keys)]
            cursor += len(request_keys)
            for expected_key, entry in zip(request_keys, entries):
                _check_storage_key(expected_key, entry)
            proofs[request] = encode_rlp_proofs(
                {"accountProof": account_proof, "storageProof": entries}
            )
        return proofs

    def _handle_failure(
        self, chunk: List[ProofRequest], exc: Exception, retried: bool
    ) -> None:
        safe_message = format_exception_safe(exc)[:200]
        if len(chunk) > 1:
            # Transport-looking errors get one retry of the same chunk;
            # size/shape errors (and second failures) are split instead.
            if not retried and not _looks_like_size_or_shape_error(exc):
                _logger.warning(
                    "Bulk eth_getProof chunk of %d requests failed (%s); "
                    "retrying once before splitting",
                    len(chunk),
                    safe_message,
                )
                self.fetch(chunk, retried=True)
                return
            self._result.stats.splits += 1
            middle = len(chunk) // 2
            _logger.warning(
                "Bulk eth_getProof chunk of %d requests failed (%s); "
                "splitting in %d + %d",
                len(chunk),
                safe_message,
                middle,
                len(chunk) - middle,
            )
            self.fetch(chunk[:middle])
            self.fetch(chunk[middle:])
            return

        request = chunk[0]
        _logger.error(
            "Proof generation failed for %s %s%s: %s",
            request.kind,
            request.gauge,
            f" / {request.user}" if request.user else "",
            safe_message,
        )
        self._result.errors[request] = exc
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._abort_after:
            self._aborted = True
            self._result.stats.aborted = True
            _logger.error(
                "Aborting bulk proof generation after %d consecutive "
                "request failures (likely provider-wide outage)",
                self._consecutive_failures,
            )
