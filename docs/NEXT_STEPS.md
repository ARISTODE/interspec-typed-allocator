# InterSpec remaining work and acceptance gates

**Snapshot 2026-11-02 UTC.** This checklist is the shared progress tracker between local Codex and ChatGPT. Statuses below reflect observed GitHub evidence at snapshot time, **not** automatic verification of future changes. Update this file in PRs with exact evidence links.

| ID | Priority | Task | Snapshot state |
| --- | --- | --- | --- |
| C0 | First | Reconcile checkout/PRs/CI and pin exact experimental source | Pending on new local Codex session |
| C1 | High | Finish original-source-only pointer provenance and actual boundary-transit census | Partial pilot |
| C2 | High | Decide and verify real-app coverage of typed pools, stack/global/T heap registration | Runtime API prototype; real integration pending |
| C3 | High | Extend differential regression, failure-path and adversarial security gates | Selected parity passes; broad coverage pending |
| C4 | High | Run controlled publication performance on dedicated host | Blocked on suitable host; [draft PR #28](https://github.com/ARISTODE/interspec-typed-allocator/pull/28) is staged |
| C5 | High | Reconcile original paper policy/PoC/coverage and remaining boundaries | Pending |
| C6 | Final | Produce return handoff for ChatGPT and present verified paper revision scope | Pending |

## C0. Establish the actual baseline

* Fetch remote refs; record clean/dirty worktree, current and base SHAs, open/merged PRs #24–28, check suites and failures. Avoid mistaking the experiment branch for `main`.
* Check that PR #26 layout tests, #25 regression fix, #27 audit and #28 workflow are available on the intended checkout. Do not assume #28 is merged because its workflow exists in a draft branch.
* Record pinned upstream revisions and toolchains in test manifests.

**Done only when:** an audited source manifest and CI inventory are linked in this ledger; no unrelated source modifications are overwritten.

## C1. Original source pointer census, not wrapper statistics

* Enumerate pointer-bearing original application API sites, including nested struct fields, callbacks, indirect pointers, error paths and global/stack data, for rsync/popt, memcached/bipbuffer, nginx/PCRE8 and any truly original YAML application source. Verify what each isolated bridge actually transports.
* Keep four separate counts: (a) original static pointer expression sites; (b) native executed source-site events by storage class and direction T→U/U→T; (c) actual isolated adapter raw pointer transit versus copied values/handles; (d) T-side consumption/dereference checks.
* Pin original upstream SHA and source line/function. Do not count project-authored adapters, injected pointers or harness-only sites; retain null/unknown/unresolved categories.
* Use and extend `tools/source_origin/README.md` and the original-source GitHub workflows. Recompute denominators and demonstrate at least representative raw evidence per category.

**Done only when:** independently checked per-boundary machine-readable raw records and source mapping tables exist, with exclusions, coverage, observed workloads, and missing categories explicit. Do not label partial 14-site pilot as exhaustive.

## C2. Extended SP3 deployment and security scope

* Review `docs/SP3_TYPED_POOL_NONHEAP.md`, `include/interspec/runtime.h`, `tests/runtime_object_layout.cpp`. Preserve existing typed allocator enforcement and fail-closed rules.
* For each observed real original pointer, decide whether the bridge copies/tokenizes it or genuinely needs raw pointer registration. **Do not introduce unsafe raw pointer transit merely to exercise the new API.**
* Where needed, integrate trusted typed array/field descriptions and scoped T heap/stack/U global registrations into the real backend; record exact type, extent, storage, domain and lifetime. Register only with trusted authority; revoke at scope exit; reject forged, expired, unaligned, cross-element, wrong-type, wrong-domain and oversized access.
* U stack registration requires authentic compiler/backend scope and lifetime metadata; do not accept a forged U-provided base, size or token. Ambiguous unions/`void*`/flexible arrays/opaque types require explicit trusted policy or honest unsupported classification.
* Repeat positive and negative runtime and application regressions for every integration change.

**Done only when:** claims are scoped to deployed application paths with test binaries, source SHA, accepted legitimate examples and denied corruptions; otherwise label as runtime-only capability.

## C3. Native-equivalence and adversarial regression

* Run matched original native, RLBox-only, tracking-only and Extended-SP3 modes with identical workloads and inputs, preserve stdout/stderr/exit codes, response bytes, returned errors, manifests and application-specific semantic results. Keep security injection binaries separate from normal behavior.
* Cover original failure paths (especially nginx PCRE8 error reason/offset), rsync option and file semantics, memcached watchers/concurrency, YAML valid/malformed parse semantics, and repeated operation/lifetime cases.
* Include positive legal stack/global copying and interior field pointers, and negative wrong-domain, wrong-type, untracked, stale, wrong-element, out-of-bounds, malformed lengths, and malicious substitutions. Prove rejection before T consumes the bad value.
* Retain failures and explain differences; a passing smoke test is not application equivalence.

**Done only when:** reproducible per-mode output diff, baseline/correctness assertions, fail-closed injection records and run/artifact URLs exist for the declared matrix.

## C4. Controlled publication evaluation

* Follow `CONTROLLED_EVALUATION.md`, `EVALUATION_COMPLETION.md` and PR #28's `CONTROLLED_GITHUB_CI.md`. Docker can provide a consistent build environment, but the timed workloads need a **dedicated measured host** with real pinned physical-core isolation, documented CPU power/load, matched builds and sufficient load generator capacity.
* Arrange user-approved dedicated runner or host; do not provision paid cloud hardware, enable self-hosted runners, or silently change publication protocol without permission.
* Run and independently verify the complete protocol. Memcached: six workloads × four modes × 15 reps, 30-second windows and warmups, plus 50-case gate. Also run Nginx, rsync/P11, YAML and all relevant microbenchmarks with documented repetitions.
* Save immutable source SHA, host inventory, raw paired samples, binary hashes, failures, artifacts, before/after host state, correctness gates and independent verifier reports.
* Re-run relevant app and microbenchmarks after deploying new typed-pool/nonheap paths; old archived measurements exclude those features. Never synthesize ZIP/libzip values or compute cross-host geomeans.

**Done only when:** raw artifacts and independent verifier outputs are archived and reviewed for provenance, repeatability, correctness and load saturation; a manual workflow file or green compilation does not satisfy this task.

## C5. Original paper claim and policy reconciliation

* Reproduce effective SP1, SP2 and SP3 controls and policy coverage on the exact paper benchmark/boundary set. Separate original domain-only SP3 from Extended SP3. Link original claimed field counts and pointer coverage to reproducible source and actual enforcement.
* Verify original ten-boundary row provenance, PoC executions, data CIV protection claims, and ZIP/libzip evidence or explicitly mark unverified/omit the unsupported row.
* Reconcile evaluated PCRE8 deployment with PCRE2 wording in the manuscript. List true limits (same-type object substitutions without identity; concurrent U modification; nonheap scope provenance; unsupported type inference and arbitrary data corruption).
* Provide draft tables/figures backed by immutable run artifacts. Keep the official paper repository unchanged until Jack reviews the proposed section changes.

**Done only when:** each proposed paper claim has a source/run/artifact pointer and any incomplete claims are explicitly flagged.

## C6. Return handoff to ChatGPT

* Update `docs/EVIDENCE_LEDGER.md` and this checklist, then complete `docs/RETURN_HANDOFF.md`, replacing all placeholders and stating exactly what remains incomplete.
* Open a PR describing implementation diffs, test commands, CI runs, raw artifact hashes, measured numbers, known counterexamples and paper impact. Do not silently merge experimental results into `main`.
* Give ChatGPT the PR URL(s), final commit(s), artifact links and the return handoff path. ChatGPT will re-audit results before resuming paper writing.

**Done only when:** another researcher can reproduce each claimed result without access to ChatGPT history, and any blockers are visible rather than hidden.
