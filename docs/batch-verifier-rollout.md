# BatchVerifier rollout — cross-repo checklist

Batched storage proofs support Curve, Balancer and FXN; Pendle/YB keep their own
verifiers, and Base/Polygon oracles are frozen. The current deployment scope is
**Curve + FXN on Arbitrum**, with a **Curve Arbitrum canary** planned. Balancer and
Optimism are outside this rollout. Updated 2026-09-23. Use the existing automation-jobs/Maestro pipeline, with legacy
insertion as the default and explicitly selected campaigns for the batch canary.
Compatible protocols automatically attempt batch artifacts alongside legacy proofs;
batch-specific failures omit that platform's bags without blocking legacy publication.
The API job uses its usual positional arguments, without bulk/batch workflow inputs.
Proof generation does not depend on deployed verifier addresses; deployment and
campaign selection are separate from artifact generation.

## Deployment snapshot — 2026-09-23

Live state checked at Arbitrum block **508120606**:

| Protocol | Chain ID | BatchVerifier | DAO owner | AllMight V2 relayer | Oracle data / block provider |
|---|---|---|---|---|---|
| Curve | 42161 | `0xd59e30FAF4113b18BFe841aF482930206522Bf46` | Confirmed | Authorized | `false` / `false` |
| FXN | 42161 | `0x1F7B08b5536AEC8952D7856b54a0d2CCd6Ab28dD` | Confirmed | Authorized | `false` / `false` |

The owner of both verifiers is DAO `0xB0552b6860CE5C0202976Db056b5e3Cc4f9CC765`.
Neither deployment is ready for batch insertion until its two Oracle roles are granted.
The FXN deployment alone does not select FXN campaigns. No Balancer or Optimism
deployment is required for the Curve canary.

## Canary selection — configured, not yet executed in production

`VOTEMARKET_BATCH_CAMPAIGNS` on automation branch `dev/votemarket-batch-verifier`
selects only the following tuple:

| Field | Value |
|---|---|
| Protocol | Curve |
| `chain_id` | `42161` (Arbitrum) |
| `votemarket_address` | `0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9` |
| `campaign_id` | `1986` |
| Gauge | `0xB84637aB9Be835580821A67823f414FFd0bbf625` |

[Campaign creation transaction](https://arbiscan.io/tx/0xaacee98421ef852509af600871d1fd770a699e9b2f343f6d5ad0bd46bf61104b).
The campaign starts on **2026-09-24 at 00:00 UTC (02:00 Paris)**, confirmed by
`campaignById(1986)` at Arbitrum block 508123755. Both Curve Oracle roles were
still `false` at that block.

The selection routes this campaign through BatchVerifier when the modified automation
runs; other campaigns retain legacy routing. It does not grant Oracle roles or
activate the verifier on-chain. Oracle authorization and production execution remain
pending, separately from the campaign's creation.

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
  All three submission functions also require an authorized relayer; the owner manages
  that allowlist. The Weiroll caller is AllMight, which must be authorized for the canary.
- `src/utils/MerklePatriciaBatchVerifier.sol` — derived from `market` @ commit `75b24ec`;
  include local library changes in the review.
- `script/verifier/DeployBatchVerifier.s.sol` — CREATE3 **protected salts** (broadcaster in the
  first 20 bytes — not squattable or front-runnable, byte 21 = 0x00 for the same address
  cross-chain), governance and anchor readiness checks, address pinning and immutable
  asserts. Its current targets are Curve and FXN on Arbitrum only. For each verifier,
  it broadcasts three separate transactions: deploy with the broadcaster as owner,
  authorize AllMight V2, then transfer ownership to the DAO. These operations are not
  atomic; check their receipts and live state after broadcasting. It prints the two
  Oracle role calls for governance without broadcasting them.
- Initial recorded results (historical): 38 test executions: differential vs legacy on real curve/balancer/fxn proofs, exclusion,
  30-account scale, bag attacks, root-registration error paths and no-op semantics.

Remaining:

- [ ] Audit — bundle with the `market` audit; state explicitly for auditors: the trust root is the
      Oracle's authorized block-number provider set. BatchVerifier refuses to overwrite a conflicting
      root, but authorized Oracle providers can change the shared root, as in the legacy design.
- [ ] Before canary activation, verify that the L1 block updater is an authorized
      block-number provider of the Curve Arbitrum Oracle and actually serves it; validate
      the deployed immutables and record addresses, salts and initcode/runtime hashes
      in the address book. After the governance calls, verify
      `authorizedDataProviders(batchVerifier) == true` and
      `authorizedBlockNumberProviders(batchVerifier) == true`. Recheck DAO ownership
      and AllMight V2's relayer authorization against the snapshot above.
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
  failures to its caller. `scripts/vm_active_proofs.py` automatically attempts complete
  artifacts for Curve/Balancer/FXN. It builds each platform's candidate privately, attaches
  only complete bags, and logs batch-specific failures while retaining unchanged legacy
  fields without optional bags for that platform. Other platforms continue independently.
  Node-collection failures invalidate bags for their block without discarding already-built
  legacy proofs. Actual proof/RPC failures retain their existing handling. No additional job
  arguments or workflow inputs are required.
- Tests: byte-for-byte parity with `BagBuilder.sol` (golden keccaks from the Foundry suite),
  RLP header boundaries, bag-contract rules, calldata-budget chunking (incl. cheap exclusion-like
  members), block isolation, platforms sharing a gauge object at different blocks, header-block
  guard, all-or-nothing coverage, mixed/missing storage roots, root mismatch split/retry,
  malformed-response retry, exception isolation and idempotency; plus an end-to-end check (`scripts/export_batch_bags.py` + a Foundry probe) where
  bags built from a live `eth_getProof` were verified by `MerklePatriciaBatchVerifier`
  (25 accounts, values equal to `eth_getStorageAt`).

Remaining:

- [ ] Existing [PR #29](https://github.com/stake-dao/votemarket-proof-toolkit/pull/29):
      cross-check `accountPaths()`/`pointPath()` against the deployed Curve and FXN
      Arbitrum contracts in `compare_bulk_proofs.py`. No producer address configuration
      or Python change is needed to generate their proofs.
- Manual Python -> Solidity end-to-end test available: `BatchVerifierFFI.t.sol` in the
      monorepo runs `test/python/generate_batch.py` inside this toolkit's environment (FFI, like the
      legacy `generate_proof.py`), builds the bags of a real Curve gauge at a recent mainnet block and
      compares the stored values with independent GaugeController getters at that block. Needs an archive
      `ETHEREUM_MAINNET_RPC_URL` and this checkout next to the monorepo; skipped otherwise.
- [ ] Published JSON grows (hex doubles each bag, gauge data is written in both the chain index
      and the gauge file): consider a dedicated artifact file if size becomes a problem.

## 3. The bot — automation-jobs (branch `dev/votemarket-batch-verifier`)

The existing production pipeline retains headers → points → accounts → campaign updates,
then claims, with Maestro and the Weiroll executor. The Guard port and its separate
orchestrator pipeline were superseded; their PRs are closed without merging.

- `ContractRegistry.VOTEMARKET_BATCH_CAMPAIGNS` selects exact records containing `chain_id`,
  `votemarket_address` and `campaign_id`; unselected campaigns use the legacy verifiers.
  The configured selection contains only Curve Arbitrum campaign 1986,
  identified above. The published production job has not activated this canary.
- Selected campaigns use BatchVerifier for their gauge points, normal bot accounts and
  required listed users. Existing account filters and claim recipients are unchanged; the
  test voter must be in `ACCOUNTS_TO_PROCESS` or a required listed account. Other campaigns
  stay on legacy; shared Oracle keys are deduplicated. A selected
  context registers the shared root once when needed, reads the explicit publication epoch
  and filters already-registered members. Pendle/YB keep their specific proof calls.
- Validate exact chain/Oracle/controller/slots, `HASH_STRUCT_BASE_SLOT`, both Oracle roles
  and agreement between the Oracle root and `storageRootByEpoch` before using a deployment.
  The configured AllMight executor must also be an authorized relayer on BatchVerifier.
- Missing deployment/roles/root, RPC errors, malformed or oversized required bags and
  incomplete needed-member coverage stop a selected batch canary; it does not silently
  change verifier. The default legacy path ignores optional batch artifacts.
  Actual Weiroll calldata size is checked; producer account-count estimates are insufficient.
- Steps 1/2/3 preserve earlier mined hashes in execution-error reports. A retry re-reads
  Oracle state. This reporting guarantee does not extend to all campaign/claim wrappers.

Remaining:

- [ ] Validate the selected API/toolkit revisions together: automatic dual output and isolated
      batch failures must be present in the toolkit actually checked out by the API job.
      Inherited campaign-identity behavior is outside these fixes.
- [ ] Check that automation-jobs' `CURVE_BATCH_VERIFIER[42161]` and
      `FXN_BATCH_VERIFIER[42161]` match the deployment snapshot. Balancer and Optimism
      remain unconfigured for this rollout. Grant and verify the two Curve Oracle roles
      before executing the Curve canary; address/tuple configuration does not grant roles.
- [ ] Review the selection of campaign 1986 and make the production jobs
      execute the coordinated revisions. Verify fresh artifacts include the campaign, then run
      its header/point/account steps and claims, and inspect persisted Oracle values. Keep the
      existing production scheduling under operator control.

The consumer still cannot detect users entirely omitted upstream; this inherited inventory
limitation is outside the fixes requested for this lot.

## 4. Governance — after audit

The two Arbitrum verifiers are deployed, owned by the DAO, and already authorize
AllMight V2 (see the dated snapshot). Oracle governance must still grant both
`setAuthorizedDataProvider(batchVerifier)` and
`setAuthorizedBlockNumberProvider(batchVerifier)` for each instance to be used.
That is **two Oracle authorization calls for the Curve canary**, or **four calls**
for both current deployments. All four flags were still `false` at block 508120606.
Verify both flags on-chain after execution. The deployment script only prints these
calls; it does not broadcast them.

These governance calls are separate from the deployment script's three transactions
per verifier (six planned transactions for Curve + FXN). Do not infer successful
completion of every transaction from contract creation or script simulation alone.
Legacy verifiers remain permissionless and are not revoked by that script; campaigns
outside the canary continue using them.

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
  tests/test_votemarket_batch_jobs.py \
  tests/test_votemarket_canary.py
```

Order: finish audit and producer readiness → validate the coordinated revisions and
deployed Curve Arbitrum configuration → grant and verify its two Oracle roles → verify
the consumer's deployed-address entries and campaign 1986 selection → run the coordinated
revisions → validate fresh artifacts, insertion and claims before widening selection. DAO
ownership and AllMight V2
relayer authorization are already confirmed in the snapshot and should be rechecked at
activation. No Balancer/Optimism deployment or Guard cutover is needed for this canary.
