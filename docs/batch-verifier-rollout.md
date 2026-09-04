# BatchVerifier rollout — cross-repo checklist

Batched storage proofs for Votemarket V2 (curve, balancer, fxn — pendle/yb keep their own
verifiers; Base/Polygon oracles are frozen). Target chains: **Arbitrum + Optimism**.
Contracts and toolkit each reviewed twice by Codex (gpt-5.6-sol, xhigh); all findings folded in below.

Measured on recorded production proofs (callee execution gas): ~148k/account vs ~790k–1.39M
legacy (−81/−89%); bag bytes −33% at 5 accounts, −45% on the 30-account fixture. **The bag rides
in calldata: split by final serialized transaction bytes, not by account count** (Arbitrum tx
limit ~95 KB → ≈20 accounts with today's trie depth; Optimism 128 KB → ≈30; treat these as
initial ceilings, re-derived weekly, never as guaranteed maxima).

## 1. `contracts-monorepo` — the contract ✅ written, ⏳ audit

Branch `feat/votemarket-verifier-v3` (uncommitted). Done:

- `src/verifiers/BatchVerifier.sol` — `registerStorageRoot(blockHeader, accountProof)` proves the
  controller storage root from the block hash anchored in the Oracle (once per epoch; after the
  first success, same-epoch calls are no-ops returning the stored root), then
  `setAccountDataBatch(gauge, epoch, accounts[], nodeBag)` / `setPointDataBatch(gauges[], epoch, nodeBag)`.
  Legacy `ALREADY_REGISTERED` semantics; only needs the Oracle data-provider role.
- `src/utils/MerklePatriciaBatchVerifier.sol` — verbatim copy of `market` @ commit `75b24ec`
  (keep byte-identical).
- `script/verifier/DeployBatchVerifier.s.sol` — CREATE3 **protected salts** (broadcaster in the
  first 20 bytes — not squattable or front-runnable, byte 21 = 0x00 for the same address
  cross-chain), governance + anchor readiness checks, cross-chain address pinning, immutable
  asserts, prints the governance calldata.
- 38 test executions: differential vs legacy on real curve/balancer/fxn proofs, exclusion,
  30-account scale, bag attacks, root-registration error paths and no-op semantics.

Remaining:

- [ ] Commit, PR.
- [ ] Audit — bundle with the `market` audit; state explicitly for auditors: the trust root is the
      Oracle's authorized block-number provider set, and registered roots are final per epoch.
- [ ] Before broadcasting the deploy: verify on both chains that the L1 block updater is an
      authorized block-number provider of each target Oracle and actually serves it; record
      addresses, salt, initcode/runtime hashes in the address book (not optional — self-serve
      users and the indexer need them). After the governance txs, verify
      `authorizedDataProviders(batchVerifier) == true`.
- [ ] Nice-to-have for audit: real balancer/fxn point-proof fixtures; exact-error test for the
      wrong-controller path.

## 2. `votemarket-proof-toolkit` — bag production ✅ written (branch `feat/bulk-getproof`)

On top of the bulk path (`get_proofs_bulk` fetches all nodes of a gauge in one
`eth_getProof`; bags cost zero extra RPC). Done:

- `proofs/generators/node_bag.py` — `encode_node_bag()` (dedupe by keccak, strict ascending
  sort, non-root nodes < 32 bytes dropped, exact RLP framing), `chunk_by_calldata_size()`
  (greedy, budget on the **encoded call**: ABI head + 32 B per member + padded bag, one minimal
  bag per chunk), per-chain budgets (90 KB Arbitrum, 124 KB Optimism, `--batch-max-bytes` /
  `VM_BATCH_MAX_BYTES` override), `supports_batch_verifier()`.
- `proofs/generators/bulk_proof.py` + `proofs/manager.py` — raw node stacks and the controller
  `storageHash` kept per request; a malformed response or one disagreeing on the pinned root is a
  retryable `ProofResponseMismatch` (single requests retry the whole call, chunks split; the
  requests still disagreeing end in `errors` and are simply absent from the published users);
  `saw_missing_storage_root` flags a run where an accepted response carried no root.
- `proofs/batch_artifacts.py` — one collector per protocol, stacks keyed by block; per-gauge
  `batch.chunks[]` (sorted accounts, **all-or-nothing** coverage, `accounts_total`) and
  per-platform `batch_points.chunks[]` (point-only bags, sorted gauges, `missing_gauges`);
  a block whose runs disagreed on the root, or where a response carried none, gets no artifacts;
  `observed_storage_root` is diagnostic only. `safe_attach_batch_artifacts` works on private
  copies of the gauge entries (the script shares cached gauge objects between platforms), only
  for a platform anchored at the chain's published header block, and can never abort the legacy
  publication. Attached by `scripts/vm_active_proofs.py` at the end of each protocol, in bulk
  mode, for curve/balancer/fxn only.
- Tests: byte-for-byte parity with `BagBuilder.sol` (golden keccaks from the Foundry suite),
  RLP header boundaries, bag-contract rules, calldata-budget chunking (incl. cheap exclusion-like
  members), block isolation, platforms sharing a gauge object at different blocks, header-block
  guard, all-or-nothing coverage, mixed/missing storage roots, root mismatch split/retry,
  malformed-response retry, exception isolation and idempotency; plus an end-to-end check (`scripts/export_batch_bags.py` + a Foundry probe) where
  bags built from a live `eth_getProof` were verified by `MerklePatriciaBatchVerifier`
  (25 accounts, values equal to `eth_getStorageAt`).

Remaining:

- [ ] Commit, PR; once a `BatchVerifier` is deployed, cross-check `accountPaths()`/`pointPath()`
      against the live contract in `compare_bulk_proofs.py`.
- [ ] Make the Python -> Solidity end-to-end check durable (commit an exported bag fixture in the
      monorepo and a Foundry test reading it) instead of the one-off probe.
- [ ] Published JSON grows (hex doubles each bag, gauge data is written in both the chain index
      and the gauge file): consider a dedicated artifact file if size becomes a problem.

## 3. The bot — `automation-guard` ✅ written (branch `feat/votemarket-proofs-guard`)

The four legacy scripts of `automation-jobs` (`votemarket/v2/proofs/1_…4_*.py`) are
ported into `stake-dao/automation-guard` as `jobs/guard_jobs/jobs/votemarket_proofs/`:
one KMS-signed, guard-routed job per chain (`votemarket-proofs-arbitrum`,
`votemarket-proofs-optimism`), steps selectable per dispatch
(`VM_PROOFS_STEP=all|headers|points|accounts|campaigns`). Nothing was removed from
`automation-jobs`; the legacy pipeline keeps running until the atomic cutover.

Done in the port:

- `weekly_data.py` reads the protocol `index.json` (one request, no GitHub contents API),
  keeps the legacy parsing and retains `batch` / `batch_points` with their published member
  order; a malformed artifact is ignored for its entry only.
- Oracle state is read through Multicall3 for the requested epoch (`epoch` dispatch input
  for a backfill), never from the chain clock; the campaigns step refuses a published
  platform the registry does not know; transactions that landed before a failure are
  reported to Maestro.
- `planning.py` (pure): headers = legacy `setBlockData` **and** `registerStorageRoot`
  (the storage root is checked on its own, so a mid-epoch rollout registers it);
  points and accounts give every needed member to the first published chunk that
  covers it and send the remainder in published order under the chunk's bag
  (already-registered members are filtered first: one would revert the call);
  what no chunk covers, `missing_gauges` and gauges without `batch` keep the
  legacy proofs; legacy proofs stay packed three per transaction, batch calls
  one per transaction.
- Node bags are used only when the chain has a `ContractRegistry.*_BATCH_VERIFIER`
  address, the manifest and the guard carry its three rules, and the oracle
  authorizes it (`VM_PROOFS_BATCH=off` forces legacy).
- The final `execute(bytes32[],bytes[])` calldata is bounded by the chain's
  transaction limit (95 KB Arbitrum / 128 KB Optimism, minus envelope): an
  oversized chunk falls back to legacy proofs, an oversized legacy pack is split.
- Test mode chains each leg behind the run's own header / root / point legs in a
  Tenderly bundle, so a full week simulates before anything landed.

Remaining:

- [ ] Ceremony: `docs/ceremonies/votemarket-proofs/` (21 rules per chain, generated);
      Optimism also needs `AllMight.allowAddress(guard v1.1)`; fund the KMS signer on both L2s.
- [ ] After the BatchVerifier deploy: address in `constants.py` + 3 rules per
      protocol in the manifest (one change; a test enforces both), `policy batch --diff`.
- [ ] Maestro: unpause `pipelines/votemarket-v2-proofs-guard.yaml` and retire the
      four legacy insert steps in the same change (canary: one `execute` dispatch
      with `step=headers` on Arbitrum first).

## 4. Governance — after audit

- [ ] `Oracle.setAuthorizedDataProvider(batchVerifier)` from BOSS (`0xB0552b…C765`):
      3 oracles (curve, balancer, fxn) × 2 chains = 6 calls (at least one tx per chain).
      Nothing revoked, fully reversible; verify the flag on-chain afterwards.

## Order

contracts (commit → PR → audit) → toolkit encoder + chunk artifacts (parallel; parity on unit
fixtures until deploy) → guard job ceremony + test dispatches → deploy + governance (readiness
checks first) → bot canary → full switch. Legacy path stays live at every step.
