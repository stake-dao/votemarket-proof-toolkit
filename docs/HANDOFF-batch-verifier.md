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

> Update 2026-09-23: the historical design below has changed. BatchVerifier now proves the
> controller root and stores it in `Oracle.epochBlockNumber(epoch).stateRootHash`; the
> `storageRootByEpoch` getter forwards that field. Registration always verifies header/account
> proof, accepts an identical root and rejects a conflicting nonzero root. Both Oracle provider
> roles and the verifier's relayer authorization for AllMight are required. Production
> integration lives in automation-jobs: legacy insertion is the default, while exact
> `(chain_id, votemarket_address, campaign_id)` selections in `VOTEMARKET_BATCH_CAMPAIGNS`
> enable a batch canary for Curve/FXN/Balancer. The producer attempts both formats, and
> batch-specific failures keep legacy publication available. See `batch-verifier-rollout.md` for the
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
`MerklePatriciaBatchVerifier`, "node bags"), while reusing the existing Oracle and production pipeline.
The tooling supports Curve, Balancer and FXN; the current deployments are **Curve + FXN on
Arbitrum**, with a **Curve Arbitrum canary** planned. Balancer and Optimism are outside this
rollout (Pendle/YB keep their own verifiers; Base/Polygon oracles are frozen). Pierre's decisions: contract lives in `contracts-monorepo` (not `market`);
`ALREADY_REGISTERED` revert semantics like the legacy verifier (no skip); no durable fork test in the PR.

## Current branches (2026-09-08)

| Repo | Branch | PR / role |
|---|---|---|
| `contracts-monorepo` | `feat/votemarket-verifier-v3` | [#502](https://github.com/stake-dao/contracts-monorepo/pull/502), verifier and tests |
| `votemarket-proof-toolkit` | `feat/bulk-getproof` | [#29](https://github.com/stake-dao/votemarket-proof-toolkit/pull/29), proofs and bags |
| `automation-jobs` | `dev/votemarket-batch-verifier` | Existing production pipeline integration |
| `api` | `feat/votemarket-proofs-bulk` | [#61](https://github.com/stake-dao/api/pull/61), artifact publication |

The Guard job and separate Maestro pipeline were superseded; their PRs were closed without
merging. Curve BatchVerifier `0xd59e30FAF4113b18BFe841aF482930206522Bf46` and FXN BatchVerifier
`0x1F7B08b5536AEC8952D7856b54a0d2CCd6Ab28dD` are now deployed on Arbitrum (42161).
At block **508120606**, checked on **2026-09-23**, both are owned by DAO
`0xB0552b6860CE5C0202976Db056b5e3Cc4f9CC765` and authorize AllMight V2. Both Oracle provider
roles remain `false` for each verifier in this snapshot. These addresses belong in the
corresponding consumer registries. `VOTEMARKET_BATCH_CAMPAIGNS` on automation branch
`dev/votemarket-batch-verifier` selects only Curve Arbitrum campaign **1986**: chain `42161`, VoteMarket
`0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9`, gauge
`0xB84637aB9Be835580821A67823f414FFd0bbf625`
([creation transaction](https://arbiscan.io/tx/0xaacee98421ef852509af600871d1fd770a699e9b2f343f6d5ad0bd46bf61104b)).
Oracle authorization and production execution remain pending. This routing configuration
neither grants Oracle roles nor activates the verifier on-chain. Proof generation is independent
of these deployed addresses.

Cross-repo checklist and deployment snapshot: [batch-verifier-rollout.md](batch-verifier-rollout.md).

### Contracts (`packages/votemarket/`)
- `src/verifiers/BatchVerifier.sol`: `registerStorageRoot(blockHeader, accountProof)` (header must hash to
  the block hash anchored in the Oracle for its epoch; controller account proven against the header's state
  root; controller root stored in `Oracle.epochBlockNumber(epoch).stateRootHash`, with
  `storageRootByEpoch` forwarding the same field), `setAccountDataBatch(gauge, epoch, accounts[], nodeBag)`, `setPointDataBatch(gauges[], epoch,
  nodeBag)`; constructor `(oracle, gaugeController, lastVoteSlot, userSlopeSlot, weightSlot,
  hashStructBaseSlot, owner)` — `true` = Curve (`RLPDecoder`), `false` = balancer/fxn (`RLPDecoderV2`);
  needs both Oracle **data-provider and block-number-provider** roles and an authorized relayer
  for all three submission functions; public `accountPaths()`/`pointPath()`; events.
- `src/utils/MerklePatriciaBatchVerifier.sol`: derived from `market` @ `75b24ec`; include local library changes in the review.
- `script/verifier/DeployBatchVerifier.s.sol`: current targets are Curve and FXN on Arbitrum.
  CREATE3 protected salts are broadcaster-prefixed, with byte 21 = 0x00. The script checks
  Oracle governance against the Arbitrum DAO, deploys with the broadcaster as owner, authorizes
  AllMight V2, then transfers ownership to the DAO. These are three separate transactions per
  verifier (six planned for the current scope), so receipts and live state must be checked.
  It prints, without broadcasting, `setAuthorizedDataProvider` and
  `setAuthorizedBlockNumberProvider` calldata: two Oracle calls per verifier, four for both
  deployments, or two for the Curve canary only. Note: salts `CurveVerifierV3`… already exist
  for the LEGACY code in `Deploy.s.sol` — hence the name BatchVerifier.
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
  (automatic for Curve/Balancer/FXN; complete optional artifacts attached per platform;
  batch-specific errors are diagnosed and isolated from legacy publication;
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
implementation keeps automation-jobs and its existing Maestro pipeline. Legacy insertion
remains the default; an explicitly selected batch canary requires valid bags and an authorized
deployment, without silently changing verifier on failure. Pendle/YB keep their specific verifiers.
Batch headers register a missing shared Oracle root, then points/accounts use the publication's
epoch and filter registered members. Writes use the existing Weiroll executor. The first three steps
retain earlier mined hashes on an execution error; this does not extend to all downstream wrappers.

## What is left

Follow the current [rollout checklist](batch-verifier-rollout.md): audit the selected revisions,
ensure the API job resolves the toolkit with automatic dual output and isolated batch failures,
run the manual recorded and mainnet-read tests, validate the deployed configuration, and grant
both Curve Oracle roles. Check that the consumer's Arbitrum Curve/FXN entries match the deployed
addresses. Review the selection of campaign 1986, make the jobs execute the coordinated
revisions, then validate fresh artifacts, insertion, Oracle values and claims. DAO ownership and
AllMight V2 authorization are already confirmed in the snapshot; recheck them before activation.
The API job needs no additional arguments or verifier addresses. No Balancer/Optimism deployment,
Guard ceremony or replacement pipeline is required for this canary.

## Gotchas
- Use `uv run --frozen` during validation to avoid changing the toolkit lockfile.

- Foundry: measure callee gas with `vm.lastCallGas()` (a `gasleft()` window over-counts caller memory
  expansion) — except after `vm.prank`, where it returns 0; `vm.revertToState` rolls back the test
  contract's storage counters; big JSON fixtures need `--gas-limit 18446744073709551615 --memory-limit
  4294967295`; no `:` in JSON keys (path selector); Arbitrum blocks break `cast run`.
- `Oracle` public getters return tuples — read structs through `IOracle(address(oracle))`.
- Keys: `.env` files hold provider keys (Alchemy, Etherscan); never print URLs, mask `/v2/<key>`.
