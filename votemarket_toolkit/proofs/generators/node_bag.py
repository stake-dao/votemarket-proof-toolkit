"""
Node bags for the ``BatchVerifier`` (batched storage proofs).

The legacy verifiers take one proof stack per storage key. The batch verifier
(``contracts-monorepo/packages/votemarket/src/verifiers/BatchVerifier.sol``)
takes one *node bag* for many keys: the unique storage-trie nodes needed to
walk every key, submitted once. Proofs of slots under the same contract share
their upper trie levels, so a bag is much smaller than the sum of the stacks
and the verifier hashes/indexes each node once.

Bag contract (enforced on-chain by ``MerklePatriciaBatchVerifier``; the
Solidity test helper ``test/utils/BagBuilder.sol`` is the reference this
module is checked against, see ``tests/unit/test_node_bag.py``):

- one RLP list whose payload is the concatenation of the node encodings
  (the nodes are RLP lists themselves; they are copied verbatim);
- nodes sorted strictly ascending by ``keccak256`` of their encoding, which
  also forbids duplicates;
- nodes whose RLP encoding is shorter than 32 bytes are embedded in their
  parent and never referenced by hash: they are omitted, except the root of
  a stack, which is always kept;
- extra nodes that no walk reaches are tolerated (they only cost calldata),
  so a bag built for a superset of accounts still verifies — but reusing a
  gauge-wide bag for a subset of accounts does not shrink the transaction.

Bags travel as transaction calldata on the L2s hosting the oracles, so
batches are cut by the size of the **encoded call** (ABI head, one word per
member, padded bag), never by the number of accounts: Arbitrum's sequencer
rejects transactions above ~95,000 bytes and Optimism above 131,072. The
default budgets leave room for the transaction envelope; the bot must still
check the final serialized transaction (a Weiroll wrapper adds more bytes).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from eth_utils import keccak
from hexbytes import HexBytes

# Protocols whose gauge controller the batch verifier can prove: the three
# Curve-family controllers (legacy or modern Vyper allocator, three vote slots
# per account). Pendle and YB have different layouts and keep their own
# verifiers.
BATCH_VERIFIER_PROTOCOLS = frozenset({"curve", "balancer", "fxn"})

# Budget for one encoded batch call (bytes), per chain: the serialized
# transaction ceiling minus headroom for the transaction envelope.
DEFAULT_CALLDATA_MAX_BYTES = 90_000
CALLDATA_MAX_BYTES_BY_CHAIN: Dict[int, int] = {
    42161: 90_000,  # Arbitrum: sequencer max tx size ~95,000 bytes
    10: 124_000,  # Optimism: 131,072-byte transaction limit
}

# ABI head of the batch calls, excluding the members and the bag payload:
# selector + static words + dynamic offsets + array lengths.
#   setAccountDataBatch(address gauge, uint256 epoch, address[] accounts, bytes nodeBag)
ACCOUNT_CALL_HEAD_BYTES = 4 + 6 * 32
#   setPointDataBatch(address[] gauges, uint256 epoch, bytes nodeBag)
POINT_CALL_HEAD_BYTES = 4 + 5 * 32

# Nodes shorter than this are inlined in their parent by the trie encoding.
EMBEDDED_NODE_MAX_BYTES = 32

BATCH_ARTIFACT_VERSION = 1

NodeStack = List[bytes]


def supports_batch_verifier(protocol: str) -> bool:
    """True when ``protocol``'s controller can be proven by the batch verifier."""
    return protocol.lower() in BATCH_VERIFIER_PROTOCOLS


def calldata_max_bytes(chain_id: Union[int, str, None]) -> int:
    """Encoded-call byte budget for a chain (conservative default otherwise)."""
    try:
        return CALLDATA_MAX_BYTES_BY_CHAIN.get(
            int(chain_id), DEFAULT_CALLDATA_MAX_BYTES
        )
    except (TypeError, ValueError):
        return DEFAULT_CALLDATA_MAX_BYTES


def normalize_stack(nodes: Iterable[Any]) -> NodeStack:
    """Raw ``eth_getProof`` nodes (hex strings or bytes) as a list of bytes."""
    return [bytes(HexBytes(node)) for node in nodes]


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


def _rlp_list_header(payload_len: int) -> bytes:
    """RLP header of a list whose payload is ``payload_len`` bytes long."""
    if payload_len < 56:
        return bytes([0xC0 + payload_len])
    length_bytes = payload_len.to_bytes(
        (payload_len.bit_length() + 7) // 8, "big"
    )
    return bytes([0xF7 + len(length_bytes)]) + length_bytes


def unique_nodes(stacks: Iterable[Sequence[bytes]]) -> Dict[bytes, bytes]:
    """Bag members keyed by keccak: deduplicated, embedded nodes dropped.

    The first node of every stack is its root and is always kept; any other
    node shorter than ``EMBEDDED_NODE_MAX_BYTES`` is inlined in its parent
    and must not be in the bag.
    """
    nodes: Dict[bytes, bytes] = {}
    for stack in stacks:
        for index, node in enumerate(stack):
            if not isinstance(node, (bytes, bytearray)):
                raise TypeError("proof nodes must be bytes")
            if index != 0 and len(node) < EMBEDDED_NODE_MAX_BYTES:
                continue
            nodes.setdefault(keccak(node), bytes(node))
    return nodes


def encode_node_bag(stacks: Iterable[Sequence[bytes]]) -> bytes:
    """Encode the proof stacks of any number of keys as one canonical bag."""
    nodes = unique_nodes(stacks)
    payload = b"".join(nodes[node_hash] for node_hash in sorted(nodes))
    return _rlp_list_header(len(payload)) + payload


def node_bag_size(stacks: Iterable[Sequence[bytes]]) -> int:
    """Byte length of ``encode_node_bag(stacks)`` without building it."""
    payload_len = sum(len(node) for node in unique_nodes(stacks).values())
    return len(_rlp_list_header(payload_len)) + payload_len


def calldata_size(head_bytes: int, member_count: int, bag_bytes: int) -> int:
    """Encoded size of a batch call: head, one word per member, padded bag."""
    padded_bag = (bag_bytes + 31) // 32 * 32
    return head_bytes + 32 * member_count + padded_bag


# ---------------------------------------------------------------------------
# Chunking by encoded call size
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BagChunk:
    """One batch call: its members (accounts or gauges, in order) and bag."""

    members: List[str]
    node_bag: bytes
    calldata_bytes: int

    def to_json(self, member_key: str) -> Dict[str, Any]:
        return {
            member_key: list(self.members),
            "node_bag": "0x" + self.node_bag.hex(),
            "bag_bytes": len(self.node_bag),
            "calldata_bytes": self.calldata_bytes,
        }


def chunk_by_calldata_size(
    members: Sequence[str],
    stacks_by_member: Dict[str, Sequence[Sequence[bytes]]],
    max_bytes: int,
    head_bytes: int = ACCOUNT_CALL_HEAD_BYTES,
) -> List[BagChunk]:
    """Cut ``members`` (in order) into calls whose encoding stays within ``max_bytes``.

    The budget applies to the whole encoded call (``calldata_size``): the ABI
    head, one word per member and the padded bag — so many cheap members
    (exclusion proofs sharing every node) are bounded too. Each chunk gets
    its own minimal bag, built only from its members' stacks. Greedy in input
    order, so the chunks are reproducible from the published member order.

    Raises:
        ValueError: A single member alone exceeds ``max_bytes`` (the budget is
            too small for this trie depth) or a member has no stacks.
    """
    if max_bytes < 1:
        raise ValueError("max_bytes must be >= 1")

    chunks: List[BagChunk] = []
    current: List[str] = []
    current_stacks: List[Sequence[bytes]] = []

    def _size(count: int, stacks: List[Sequence[bytes]]) -> int:
        return calldata_size(head_bytes, count, node_bag_size(stacks))

    for member in members:
        stacks = stacks_by_member.get(member)
        if not stacks:
            raise ValueError(f"No proof stacks for {member}")
        if _size(1, list(stacks)) > max_bytes:
            raise ValueError(
                f"Batch call for {member} alone exceeds the "
                f"{max_bytes}-byte calldata budget"
            )
        candidate = current_stacks + list(stacks)
        if current and _size(len(current) + 1, candidate) > max_bytes:
            chunks.append(_chunk(current, current_stacks, head_bytes))
            current, current_stacks = [], []
            candidate = list(stacks)
        current.append(member)
        current_stacks = candidate
    if current:
        chunks.append(_chunk(current, current_stacks, head_bytes))
    return chunks


def _chunk(
    members: List[str], stacks: List[Sequence[bytes]], head_bytes: int
) -> BagChunk:
    bag = encode_node_bag(stacks)
    return BagChunk(
        members, bag, calldata_size(head_bytes, len(members), len(bag))
    )


def batch_artifact(
    chunks: Sequence[BagChunk],
    member_key: str,
    observed_storage_root: Optional[bytes],
    **extra: Any,
) -> Dict[str, Any]:
    """Versioned JSON artifact published next to the legacy proofs.

    ``observed_storage_root`` is diagnostic only: the batch verifier proves
    and stores its own root from the anchored block header; consumers may
    compare this value with ``storageRootByEpoch`` but must never rely on it.
    """
    artifact: Dict[str, Any] = {
        "version": BATCH_ARTIFACT_VERSION,
        "verifier": "BatchVerifier",
        "observed_storage_root": (
            "0x" + observed_storage_root.hex()
            if observed_storage_root
            else None
        ),
        "chunks": [chunk.to_json(member_key) for chunk in chunks],
    }
    artifact.update(extra)
    return artifact
