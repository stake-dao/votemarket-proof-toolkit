---
name: handoff-batch-verifier
description: "Full hand-off of the BatchVerifier project (2026-08-31 to 2026-09-03) for a new session — state per repo, decisions, measurements, what is left, gotchas"
metadata: 
  node_type: memory
  type: project
  originSessionId: 05b14ad1-6dcf-48ed-9887-407a35d4d9b8
  modified: 2026-09-03T08:29:54.242Z
---

# Hand-off — Votemarket V2 batched proofs (BatchVerifier)

Read this first, then the linked notes for details: [[market-node-bag-plan]], [[verifier-v3-implementation]],
[[toolkit-batch-artifacts]], [[v2-verifier-gas-measurements]], [[fork-rehearsal]], [[bulk-getproof-branch]],
[[alchemy-limits]], [[user-profile]].

## Goal

Cut the cost and transaction count of inserting Votemarket V2 storage proofs (Curve-family gauge
controllers) by reusing Warren's batched Merkle-Patricia library (`market` repo,
`MerklePatriciaBatchVerifier`, "node bags"), without touching anything deployed. Scope: **curve,
balancer, fxn** on **Arbitrum + Optimism** (pendle/yb keep their own verifiers; Base/Polygon oracles
are frozen). Pierre's decisions: contract lives in `contracts-monorepo` (not `market`);
`ALREADY_REGISTERED` revert semantics like the legacy verifier (no skip); no durable fork test in the PR.

## State per repo (2026-09-03)

| Repo | Branch | Commit | PR | Status |
|---|---|---|---|---|
| `~/Documents/apps/contracts-monorepo` | `feat/votemarket-verifier-v3` (from origin/main fe9022dc) | `a861db84` | https://github.com/stake-dao/contracts-monorepo/pull/502 (draft) | done, awaiting audit |
| `~/Documents/apps/votemarket-proof-toolkit` | `feat/bulk-getproof` | `715f039` (on top of 8 bulk commits) | https://github.com/stake-dao/votemarket-proof-toolkit/pull/29 (draft) | done |
| `~/Documents/apps/automation-jobs` | — | — | — | untouched (legacy keeps running until cutover) |
| `~/Documents/apps/automation-guard` | `feat/votemarket-proofs-guard` (from origin/main 0fb4743) | see PR | draft PR (2026-09-04) | job written, ceremony drafted, awaiting Safe |
| `~/Documents/apps/orchestrator` | `feat/votemarket-proofs-guard` | — | — | paused Maestro twin `pipelines/votemarket-v2-proofs-guard.yaml` |
| `~/Documents/apps/api` | `feat/votemarket-proofs-bulk` (local only) | uncommitted | — | `--bulk-proofs` wiring, test from the api repo before merging (Quentin) |

Cross-repo checklist: `votemarket-proof-toolkit/docs/batch-verifier-rollout.md` (committed).

### Contracts (`packages/votemarket/`)
- `src/verifiers/BatchVerifier.sol`: `registerStorageRoot(blockHeader, accountProof)` (header must hash to
  the block hash anchored in the Oracle for its epoch; controller account proven against the header's state
  root; root stored per epoch, final once registered — the Oracle's overloaded `stateRootHash` field is
  never read), `setAccountDataBatch(gauge, epoch, accounts[], nodeBag)`, `setPointDataBatch(gauges[], epoch,
  nodeBag)`; constructor `(oracle, gaugeController, lastVoteSlot, userSlopeSlot, weightSlot,
  legacyStructSlot)` — `true` = Curve (`RLPDecoder`), `false` = balancer/fxn (`RLPDecoderV2`); only needs
  the Oracle **data-provider** role; public `accountPaths()`/`pointPath()`; events.
- `src/utils/MerklePatriciaBatchVerifier.sol`: verbatim copy of `market` @ `75b24ec` (keep byte-identical).
- `script/verifier/DeployBatchVerifier.s.sol`: CREATE3 protected salts (broadcaster-prefixed, byte 21 =
  0x00), governance == BOSS `0xB0552b6860CE5C0202976Db056b5e3Cc4f9CC765` check, prints
  `setAuthorizedDataProvider` calldata. Note: salts `CurveVerifierV3`… already exist for the LEGACY code
  in `Deploy.s.sol` — hence the name BatchVerifier.
- 38 Foundry tests (`test/unit/oracle/BatchVerifier.t.sol`), fixtures `data/proofs/1730937600` (Curve, same as
  market's), `1785974400` (balancer/fxn era fixtures from market), `1787788800/curve_batch.json` (30 real
  accounts, exclusion, 5 points, generated). Package suite: 113 pass + 6 pre-existing FFI failures
  (`Platforms.sol`, need `ALCHEMY_KEY`).

### Toolkit
- `votemarket_toolkit/proofs/generators/node_bag.py` (encoder, `chunk_by_calldata_size`, budgets 90 KB
  Arbitrum / 124 KB Optimism, heads 196/164 B), `proofs/generators/bulk_proof.py` + `proofs/manager.py`
  (raw node stacks, pinned `storageHash`, retryable `ProofResponseMismatch`, `saw_missing_storage_root`),
  `proofs/batch_artifacts.py` (collector per protocol keyed by block, all-or-nothing per gauge, private
  copies per platform, header-block guard, exception boundary), `scripts/vm_active_proofs.py`
  (`--bulk-proofs` required; artifacts attached at end of protocol; `--batch-max-bytes`),
  `scripts/export_batch_bags.py` (real bags for a Foundry check).
- Published JSON: per gauge `batch{version, block_number, accounts_total, observed_storage_root,
  chunks[{accounts, node_bag, bag_bytes, calldata_bytes}]}`; per platform `batch_points{…, missing_gauges,
  chunks[{gauges, node_bag, …}]}` in `<platform>/<chain>/index.json`. Legacy fields untouched.
- Tests: 115 in the bulk/bag files (golden parity with `BagBuilder.sol`), suite 175 pass + 14 pre-existing
  failures. README section "Batch verifier artifacts (node bags)".

## Measurements (all on real data)
- Deployed legacy Verifier on Arbitrum `0xC727…D2d9`: 1.39M gas/account (current source builds to 790k —
  deployed bytecode is an older build, ask Warren). BatchVerifier: ~148k/account (−89%); points 294k → 87k.
- Weekly cost today (Arbitrum, week of 2026-08-27): 65 txs, 129 setAccountData + 62 setPointData,
  0.0045 ETH (~$11). Economics are small; value is operational (65 → ~15 txs/week) — Pierre knows.
- Bags: ~20 accounts/tx on Arbitrum (95 KB limit), ~30 on Optimism.
- **Fork rehearsal 2026-09-03** (Arbitrum fork, real Curve Oracle `0x36F5…`, real platform `0x8c2c…`):
  `registerStorageRoot` == the root the legacy verifier stored that week; 110 accounts inserted via batch
  with values identical to the deployed legacy verifier; real `Votemarket.claim` identical per account
  (campaign 1623: 29 claimers, 10,896.88 pSDT); −89.8% gas. Test files kept only in the job tmp dir
  (Pierre chose not to add them to the PR).

## Guard port (2026-09-04)

The bot lives in `automation-guard` (`jobs/guard_jobs/jobs/votemarket_proofs/`): one KMS-signed,
guard-routed module per chain (`votemarket-proofs-arbitrum`, `votemarket-proofs-optimism`), the four
legacy steps selectable per dispatch (`VM_PROOFS_STEP`), node-bag path gated on a deployed
`ContractRegistry.*_BATCH_VERIFIER` + manifest/guard rules + oracle authorization (legacy verifiers
otherwise, `VM_PROOFS_BATCH=off` forces legacy). Rehearsed 2026-09-04 on Arbitrum with real proofs and
DRY_RUN: 64 txs for the week (2 headers, 22 point packs, 40 account packs), max calldata 22 KB, all
reads verified against the live oracle (60/60 points, 106/106 accounts already inserted by the legacy
bot). Ceremony JSON generated (`docs/ceremonies/votemarket-proofs/`, 21 + 18 `setRule`); Optimism also
needs `AllMight.allowAddress(guard v1.1)`; the signer holds 0 ETH on both L2s. Two platform edits:
`EXECUTOR_GUARD_DEPLOY_BLOCK` for 42161/10 and the `chain_id == 1` assertion relaxed to "has a Boss
Safe". Pre-existing on origin/main: `crv-swaps.yaml` drifts from its manifest (2 platform tests red),
2 ruff findings in files untouched here.

## What is left
1. **Bot** — done in `automation-guard` (above); after the BatchVerifier deploy add its address to
   `constants.py` and the 9 rules per chain to the manifest in one change (test-enforced), regenerate
   the ceremony. The plan below was written for `automation-jobs` and is superseded by the guard port
   (kept for the intent): constants +
   ABI; `weekly_data_processor.py` dataclasses for `batch`/`batch_points` (keep chunk account order);
   `1_insert_headers.py` check `storageRootByEpoch` independently of the legacy header, then
   `registerStorageRoot`; `2_insert_point_data.py` `setPointDataBatch` (`missing_gauges` → legacy);
   `3_insert_accounts.py` filter registered accounts (one registered account reverts the chunk), send each
   chunk's remaining accounts in published order with the chunk's bag, refetch+retry on
   `ALREADY_REGISTERED`, legacy path when no `batch`; `common.py` send batch calls **directly** to the
   BatchVerifier as a `Calldata` (no Weiroll wrapping, 1 batch per tx). Canary 1 gauge on Arbitrum.
2. Ask Warren: include BatchVerifier in the Market audit? why is the deployed Verifier not the current
   source build (redeploying the current legacy build alone = −43%)?
3. After audit: deploy script, 6 governance calls (3 oracles × 2 chains), address-book entries.
4. Bot RPC: the prod Alchemy key must serve `eth_getProof` at the Oracle-anchored block (~2,000 blocks
   deep); the Free tier does not (~128 blocks). A dRPC key worked (archive).

## Gotchas
- Every `uv run` rewrites `uv.lock` in the toolkit: `git checkout -- uv.lock` before committing; never
  `git stash` with a dirty lockfile (pop conflicts).
- Codex reviews: always `--model gpt-5.6-sol --effort xhigh` (Pierre's rule). The plugin wrapper loses jobs
  past 10 min: poll `node ~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs
  status --all --json` from the workspace that launched it, then `result <id>`; if a job hangs (no
  transcript events for >30 min in `~/.codex/sessions/`), `cancel <id>` then `task --background
  --resume-last "…"`. Codex desktop app sessions also appear in `~/.codex/sessions` — don't confuse them.
- Foundry: measure callee gas with `vm.lastCallGas()` (a `gasleft()` window over-counts caller memory
  expansion) — except after `vm.prank`, where it returns 0; `vm.revertToState` rolls back the test
  contract's storage counters; big JSON fixtures need `--gas-limit 18446744073709551615 --memory-limit
  4294967295`; no `:` in JSON keys (path selector); Arbitrum blocks break `cast run`.
- `Oracle` public getters return tuples — read structs through `IOracle(address(oracle))`.
- Keys: `.env` files hold provider keys (Alchemy, Etherscan); never print URLs, mask `/v2/<key>`.
