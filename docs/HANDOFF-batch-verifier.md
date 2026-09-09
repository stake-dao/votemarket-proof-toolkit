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

> Update 2026-09-08: the historical design below has changed. BatchVerifier now proves the
> controller root and stores it in `Oracle.epochBlockNumber(epoch).stateRootHash`; the
> `storageRootByEpoch` getter forwards that field. Registration always verifies header/account
> proof, accepts an identical root and rejects a conflicting nonzero root. Both Oracle provider
> roles are required. Production integration now lives in automation-jobs with mandatory batch
> proofs for Curve/FXN/Balancer and no legacy fallback. See `batch-verifier-rollout.md` for the
> current contract authorization requirements; the Guard rollout and old measurements below
> are historical context.
>
> The constructor's `hashStructBaseSlot` flag is immutable after deployment and exposed by
> `HASH_STRUCT_BASE_SLOT()`. `true` (Curve) adds one hash of the nested struct base before field
> offsets; `false` (FXN/Balancer) uses that base directly. It applies to `vote_user_slopes` and
> `points_weight`, never to `last_user_vote`. Both layouts still hash each final field slot into
> its storage-trie path. This selects the controller's storage layout; it does not select a verifier
> or enable a legacy fallback.

Read this first, then the linked notes for details: [[market-node-bag-plan]], [[verifier-v3-implementation]],
[[toolkit-batch-artifacts]], [[v2-verifier-gas-measurements]], [[fork-rehearsal]], [[bulk-getproof-branch]],
[[alchemy-limits]], [[user-profile]].

## Goal

Cut the cost and transaction count of inserting Votemarket V2 storage proofs (Curve-family gauge
controllers) by reusing Warren's batched Merkle-Patricia library (`market` repo,
`MerklePatriciaBatchVerifier`, "node bags"), while reusing the existing Oracle and production pipeline. Scope: **curve,
balancer, fxn** on **Arbitrum + Optimism** (pendle/yb keep their own verifiers; Base/Polygon oracles
are frozen). Pierre's decisions: contract lives in `contracts-monorepo` (not `market`);
`ALREADY_REGISTERED` revert semantics like the legacy verifier (no skip); no durable fork test in the PR.

## Current branches (2026-09-08)

| Repo | Branch | PR / role |
|---|---|---|
| `contracts-monorepo` | `feat/votemarket-verifier-v3` | [#502](https://github.com/stake-dao/contracts-monorepo/pull/502), verifier and tests |
| `votemarket-proof-toolkit` | `feat/bulk-getproof` | [#29](https://github.com/stake-dao/votemarket-proof-toolkit/pull/29), proofs and bags |
| `automation-jobs` | `dev/votemarket-batch-verifier` | Existing production pipeline integration |
| `api` | `feat/votemarket-proofs-bulk` | [#61](https://github.com/stake-dao/api/pull/61), artifact publication |

The Guard job and separate Maestro pipeline were superseded; their PRs were closed without
merging. No deployment or Oracle authorization is established by these changes. The three
BatchVerifier address registries in automation-jobs remain empty.

Cross-repo checklist: `votemarket-proof-toolkit/docs/batch-verifier-rollout.md` (committed).

### Contracts (`packages/votemarket/`)
- `src/verifiers/BatchVerifier.sol`: `registerStorageRoot(blockHeader, accountProof)` (header must hash to
  the block hash anchored in the Oracle for its epoch; controller account proven against the header's state
  root; controller root stored in `Oracle.epochBlockNumber(epoch).stateRootHash`, with
  `storageRootByEpoch` forwarding the same field), `setAccountDataBatch(gauge, epoch, accounts[], nodeBag)`, `setPointDataBatch(gauges[], epoch,
  nodeBag)`; constructor `(oracle, gaugeController, lastVoteSlot, userSlopeSlot, weightSlot,
  hashStructBaseSlot)` — `true` = Curve (`RLPDecoder`), `false` = balancer/fxn (`RLPDecoderV2`); needs both
  Oracle **data-provider and block-number-provider** roles; public `accountPaths()`/`pointPath()`; events.
- `src/utils/MerklePatriciaBatchVerifier.sol`: derived from `market` @ `75b24ec`; include local library changes in the review.
- `script/verifier/DeployBatchVerifier.s.sol`: CREATE3 protected salts (broadcaster-prefixed, byte 21 =
  0x00), governance == BOSS `0xB0552b6860CE5C0202976Db056b5e3Cc4f9CC765` check, prints
  `setAuthorizedDataProvider` and `setAuthorizedBlockNumberProvider` calldata. Note: salts `CurveVerifierV3`… already exist for the LEGACY code
  in `Deploy.s.sol` — hence the name BatchVerifier.
- Initial recorded test results (historical): 38 Foundry tests (`test/unit/oracle/BatchVerifier.t.sol`), fixtures `data/proofs/1730937600` (Curve, same as
  market's), `1785974400` (balancer/fxn era fixtures from market), `1787788800/curve_batch.json` (30 real
  accounts, exclusion, 5 points, generated). Package suite: 113 pass + 6 pre-existing FFI failures
  (`Platforms.sol`, need `ALCHEMY_KEY`).

### Toolkit
- `votemarket_toolkit/proofs/generators/node_bag.py` (encoder, `chunk_by_calldata_size`, budgets 90 KB
  Arbitrum / 124 KB Optimism, heads 196/164 B), `proofs/generators/bulk_proof.py` + `proofs/manager.py`
  (raw node stacks, pinned `storageHash`, retryable `ProofResponseMismatch`, `saw_missing_storage_root`),
  `proofs/batch_artifacts.py` (collector per protocol keyed by block, all-or-nothing per gauge, private
  copies per platform, header-block guard, exception boundary), `scripts/vm_active_proofs.py`
  (automatic for Curve/Balancer/FXN; complete artifacts required before protocol output;
  optional `--batch-max-bytes` tuning),
  `scripts/export_batch_bags.py` (real bags for a Foundry check).
- Published JSON: per gauge `batch{version, block_number, accounts_total, observed_storage_root,
  chunks[{accounts, node_bag, bag_bytes, calldata_bytes}]}`; per platform `batch_points{…, missing_gauges,
  chunks[{gauges, node_bag, …}]}` in `<platform>/<chain>/index.json`. Legacy fields untouched.
- Initial test results (historical): 115 in the bulk/bag files (golden parity with `BagBuilder.sol`), suite 175 pass + 14 pre-existing
  failures. README section "Batch verifier artifacts (node bags)".

## Historical measurements (earlier builds; remeasure current revisions)
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

## Historical Guard port (superseded)

The Guard job and its separate Maestro pipeline were an earlier integration experiment. Their
ceremony, fallback mode and activation steps are no longer part of this rollout. The current
implementation keeps automation-jobs and its existing Maestro pipeline. Compatible protocols
always use BatchVerifier, with no legacy fallback; Pendle/YB keep their specific verifiers.
Headers register a missing shared Oracle root, then points/accounts use the publication's epoch
and filter registered members. Writes use the existing Weiroll executor. The first three steps
retain earlier mined hashes on an execution error; this does not extend to all downstream wrappers.

## What is left

Follow the current [rollout checklist](batch-verifier-rollout.md): audit the selected revisions,
ensure the API job resolves the toolkit with automatic batch generation and strict publication,
run the manual recorded and mainnet-read tests, deploy, grant both Oracle roles, populate the
consumer's registries and validate a canary through the existing pipeline. The API job needs
no additional arguments. No Guard ceremony or replacement pipeline is required.

## Gotchas
- Use `uv run --frozen` during validation to avoid changing the toolkit lockfile.

- Foundry: measure callee gas with `vm.lastCallGas()` (a `gasleft()` window over-counts caller memory
  expansion) — except after `vm.prank`, where it returns 0; `vm.revertToState` rolls back the test
  contract's storage counters; big JSON fixtures need `--gas-limit 18446744073709551615 --memory-limit
  4294967295`; no `:` in JSON keys (path selector); Arbitrum blocks break `cast run`.
- `Oracle` public getters return tuples — read structs through `IOracle(address(oracle))`.
- Keys: `.env` files hold provider keys (Alchemy, Etherscan); never print URLs, mask `/v2/<key>`.
