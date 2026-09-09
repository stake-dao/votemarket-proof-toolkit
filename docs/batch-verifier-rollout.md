# BatchVerifier rollout — cross-repo checklist

Batched storage proofs for Votemarket V2 (curve, balancer, fxn — pendle/yb keep their own
verifiers; Base/Polygon oracles are frozen). Target chains: **Arbitrum + Optimism**.
Updated 2026-09-09. Use the existing automation-jobs/Maestro pipeline. Compatible protocols
now generate batch artifacts automatically and the producer rejects incomplete bags before
writing that protocol. The API job uses its usual positional arguments, without bulk/batch
workflow inputs. Activate only after the selected toolkit and API revisions contain both changes.

Historical measurements on earlier builds (callee execution gas; remeasure current revisions): ~148k/account vs ~790k–1.39M
legacy (−81/−89%); bag bytes −33% at 5 accounts, −45% on the 30-account fixture. **The bag rides
in calldata: split by final serialized transaction bytes, not by account count** (Arbitrum tx
limit ~95 KB → ≈20 accounts with today's trie depth; Optimism 128 KB → ≈30; treat these as
initial ceilings, re-derived weekly, never as guaranteed maxima).

## 1. `contracts-monorepo` — the contract ✅ written, ⏳ audit

Branch `feat/votemarket-verifier-v3`, [PR #502](https://github.com/stake-dao/contracts-monorepo/pull/502). Implemented:

- `src/verifiers/BatchVerifier.sol` — `registerStorageRoot(blockHeader, accountProof)` proves the
  controller storage root from the block hash anchored in the Oracle and writes it to
  `Oracle.epochBlockNumber(epoch).stateRootHash`. Every registration revalidates the header and
  account proof; an identical root is a no-op and a conflicting nonzero root reverts. Then
  `setAccountDataBatch(gauge, epoch, accounts[], nodeBag)` / `setPointDataBatch(gauges[], epoch, nodeBag)`.
  Legacy `ALREADY_REGISTERED` semantics; needs both Oracle data-provider and block-number-provider
  roles. `storageRootByEpoch` forwards the Oracle root, with no separate local mapping.
- `src/utils/MerklePatriciaBatchVerifier.sol` — derived from `market` @ commit `75b24ec`;
  include local library changes in the review.
- `script/verifier/DeployBatchVerifier.s.sol` — CREATE3 **protected salts** (broadcaster in the
  first 20 bytes — not squattable or front-runnable, byte 21 = 0x00 for the same address
  cross-chain), governance + anchor readiness checks, cross-chain address pinning, immutable
  asserts, prints the governance calldata.
- Initial recorded results (historical): 38 test executions: differential vs legacy on real curve/balancer/fxn proofs, exclusion,
  30-account scale, bag attacks, root-registration error paths and no-op semantics.

Remaining:

- [ ] Audit — bundle with the `market` audit; state explicitly for auditors: the trust root is the
      Oracle's authorized block-number provider set. BatchVerifier refuses to overwrite a conflicting
      root, but authorized Oracle providers can change the shared root, as in the legacy design.
- [ ] Before broadcasting the deploy: verify on both chains that the L1 block updater is an
      authorized block-number provider of each target Oracle and actually serves it; record
      addresses, salt, initcode/runtime hashes in the address book (not optional — self-serve
      users and the indexer need them). After the governance txs, verify
      `authorizedDataProviders(batchVerifier) == true` and
      `authorizedBlockNumberProviders(batchVerifier) == true`.
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
  for a platform anchored at the chain's published header block. The reusable builder reports
  failures to its caller. `scripts/vm_active_proofs.py` automatically collects and requires
  complete artifacts for Curve/Balancer/FXN before writing each protocol; a failure exits
  nonzero and stops the API job before copying the generated files. No additional job
  arguments or workflow inputs are required. The API job must resolve the toolkit revision
  containing this automatic generation and strict publication check before activation.
- Tests: byte-for-byte parity with `BagBuilder.sol` (golden keccaks from the Foundry suite),
  RLP header boundaries, bag-contract rules, calldata-budget chunking (incl. cheap exclusion-like
  members), block isolation, platforms sharing a gauge object at different blocks, header-block
  guard, all-or-nothing coverage, mixed/missing storage roots, root mismatch split/retry,
  malformed-response retry, exception isolation and idempotency; plus an end-to-end check (`scripts/export_batch_bags.py` + a Foundry probe) where
  bags built from a live `eth_getProof` were verified by `MerklePatriciaBatchVerifier`
  (25 accounts, values equal to `eth_getStorageAt`).

Remaining:

- [ ] Existing [PR #29](https://github.com/stake-dao/votemarket-proof-toolkit/pull/29):
      once a `BatchVerifier` is deployed, cross-check `accountPaths()`/`pointPath()`
      against the live contract in `compare_bulk_proofs.py`.
- Manual Python -> Solidity end-to-end test available: `BatchVerifierFFI.t.sol` in the
      monorepo runs `test/python/generate_batch.py` inside this toolkit's environment (FFI, like the
      legacy `generate_proof.py`), builds the bags of a real Curve gauge at a recent mainnet block and
      compares the stored values with independent GaugeController getters at that block. Needs an archive
      `ETHEREUM_MAINNET_RPC_URL` and this checkout next to the monorepo; skipped otherwise.
- [ ] Published JSON grows (hex doubles each bag, gauge data is written in both the chain index
      and the gauge file): consider a dedicated artifact file if size becomes a problem.

## 3. The bot — automation-jobs (branch `dev/votemarket-batch-verifier`)

The existing production pipeline retains headers → points → accounts → campaign updates,
then claims, with the existing Maestro configuration and Weiroll executor. The Guard port
and its separate orchestrator pipeline were superseded; their PRs are closed without merging.
No Guard ceremony, fallback switch or replacement pipeline is required.

- Curve, Balancer and FXN require BatchVerifier. Headers call only `registerStorageRoot`
  when the Oracle's controller root is absent; points/accounts read the explicit publication
  epoch and select only missing members. Pendle/YB keep their specific proof calls.
- Validate exact chain/Oracle/controller/slots, `HASH_STRUCT_BASE_SLOT`, both Oracle roles
  and agreement between the Oracle root and `storageRootByEpoch` before using a deployment.
- Missing deployment/roles/root, RPC errors, malformed or oversized required bags and
  incomplete needed-member coverage stop the job. Legacy blobs are never a fallback.
  Actual Weiroll calldata size is checked; producer account-count estimates are insufficient.
- Steps 1/2/3 preserve earlier mined hashes in execution-error reports. A retry re-reads
  Oracle state. This reporting guarantee does not extend to all campaign/claim wrappers.

Remaining:

- [ ] Validate the selected API/toolkit revisions together: automatic batches and strict
      publication must be present in the toolkit actually checked out by the API job.
      Inherited campaign-identity behavior is outside these fixes.
- [ ] Deploy and authorize the selected contract revision, then populate automation-jobs'
      `CURVE_BATCH_VERIFIER`, `BALANCER_BATCH_VERIFIER` and `FXN_BATCH_VERIFIER` registries.
      They are currently empty; an active compatible protocol intentionally fails without one.
- [ ] Check the existing Maestro pipeline's status and rollout configuration, then run a
      canary through its header/point/account steps and inspect persisted Oracle values.

The consumer still cannot detect users entirely omitted upstream; this inherited inventory
limitation is outside the fixes requested for this lot.

## 4. Governance — after audit

No deployment or authorization is established by this document. After deployment, Oracle
governance grants both `setAuthorizedDataProvider(batchVerifier)` and
`setAuthorizedBlockNumberProvider(batchVerifier)` for each target instance: three protocol
Oracles × two chains × two roles = **12 authorization calls** for the full scope. Verify both
flags on-chain. The deployment script prints these calls; it does not execute governance.
Legacy verifiers are not revoked by that script, but the migrated job never selects them for
compatible protocols.

## Manual validation and order

Keep tests as manual commands against the selected toolkit/contracts revisions. The
[README](../README.md#proof-regression-tests) gives the deterministic Python-to-Solidity
command. From `contracts-monorepo/packages/votemarket`, run:

```sh
forge test --match-path test/unit/oracle/BatchVerifier.t.sol

VOTEMARKET_TOOLKIT_PATH=/absolute/path/to/votemarket-proof-toolkit \
REQUIRE_BATCH_VERIFIER_MAINNET_TEST=true PYTHON_DOTENV_DISABLED=1 \
forge test --match-contract BatchVerifierMainnetTest -vv
```

For the second command, provide `ETHEREUM_MAINNET_RPC_URL` in the environment. It needs
historical getters and `eth_getProof`. The Curve/FXN tests generate proofs through Python,
write to a local verifier/Oracle and compare final votes; no fork, signing or broadcast is
used. An absent RPC fails the required run. From automation-jobs, run:

```sh
PYTHON_DOTENV_DISABLED=1 PYTHONPATH=script python -m pytest -q \
  tests/test_votemarket_batch_artifacts.py \
  tests/test_votemarket_batch.py \
  tests/test_votemarket_batch_jobs.py
```

Order: finish audit and producer readiness → validate the coordinated revisions → deploy
and verify immutables → grant both Oracle roles → populate consumer registries → existing
pipeline canary → full activation. Use the current branches; no Guard cutover is involved.
