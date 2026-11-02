# InterSpec: local Codex and ChatGPT handoff

**Snapshot:** 2026-11-02 UTC. This is a historical checkpoint, not a guarantee about the current remote HEAD. Before starting, inspect live GitHub status and update the checkpoint. **Paper editing is intentionally deferred.**

## Repositories and starting point

* Implementation and experiments: [ARISTODE/interspec-typed-allocator](https://github.com/ARISTODE/interspec-typed-allocator) (public; default `main`).
* Official manuscript: [ARISTODE/Automatic-Access-Policy-Enforcement](https://github.com/ARISTODE/Automatic-Access-Policy-Enforcement) (private; leave unchanged until scientific gates pass).
* Active experiment: `experiment/original-source-provenance-20261031`, the head of [draft PR #24](https://github.com/ARISTODE/interspec-typed-allocator/pull/24), snapshot `be9947e8bd23213a6280c8ca272c1db4b7d2b90e`. Do not mistake this for `main`.
* Runtime object-layout and nonheap registration extension: [PR #26](https://github.com/ARISTODE/interspec-typed-allocator/pull/26), merged into the experiment branch, **not evidence of deployment-wide app instrumentation**.
* Historical hosted result audit: [PR #27](https://github.com/ARISTODE/interspec-typed-allocator/pull/27), merged into the same experiment branch, **not controlled publication performance**.
* Controlled evaluation infrastructure: [draft PR #28](https://github.com/ARISTODE/interspec-typed-allocator/pull/28), branch `experiment/controlled-evaluation-ci-20261101` at snapshot `7f284776355d6b3b11efd0ebab5c0c10d0542aa3`. Workflow staged, not dispatched. Read `CONTROLLED_GITHUB_CI.md` on that branch.

For local Codex, clone the implementation repository, fetch all remote refs, switch to the intended experimental or handoff branch, inspect `git status`, then run `codex`. Read `AGENTS.md`, this file, `EVIDENCE_LEDGER.md` and `NEXT_STEPS.md` first. A basic `git clone` of the default branch alone will not check out the active SP3 experiment.

## Research goal and threat model

InterSpec infers and enforces policies at the trusted (T) / untrusted (U) interface, using LLVM/data dependence analysis and RLBox isolation. SP1 limits U reads; SP2 limits writes copied back to T; SP3 constrains pointers T is prepared to consume.

For Extended SP3, T owns the live metadata table with records such as `{base, size, type_hash, site_id}`, populated through authorized allocation sites. Checks include expected domain, trusted allocation type, spatial extent and liveness/registration. A missing record must be rejected. U is treated as adversarial, even when its current tests are benign. Existing copy-based bridges and top-level T pointer bindings must be reviewed when describing the actual attack surface. Same-type substitution, temporal address identity, arbitrary data integrity, races between validation and use, unknown `void*` and unions, and broad CFI are not automatically solved.

[`docs/SP3_TYPED_POOL_NONHEAP.md`](SP3_TYPED_POOL_NONHEAP.md) describes new typed arrays, element/field checks, exact non-power-of-two stride and alignment, optional trusted object identity, and scoped external T heap/stack/U global registrations. These APIs have runtime tests. They are NOT yet systematically wired to real application interfaces. Ordinary SP3 checks do not accept raw untracked stack/global pointers.

## Selected implemented and evaluated boundaries

| Boundary | Relevant evidence | Important limitation |
| --- | --- | --- |
| rsync / popt | Actual RLBox wasm2c bridge, rsync application and corruption regressions, native comparison | `poptStrerror` remains a T host helper; isolate `poptBadOption` provenance separately |
| memcached / bipbuffer | Real cache application, watcher paths, four variants, native parity pilots | Original T stack inputs copied to U; new nonheap APIs not generally deployed |
| nginx / PCRE8 | Real Nginx/PCRE8 bridge, valid/invalid regex parity, fixed diagnostic lifetime | Evaluated PCRE8, not the manuscript's PCRE2 PoC; do not generalize to PCRE2/JIT/TLS |
| YAML / libyaml | Real isolated libyaml with a project-authored driver, semantic comparisons | Driver does not demonstrate original external application's source pointer prevalence |

The original paper may include additional boundaries (for example ZIP/libzip); new experiments on four selected boundaries do not validate all original ten-boundary manuscript rows.

## Snapshot of progress and scientific gates

1. **Implemented and tested in its stated scope:** wasm2c Extended-SP3 runtime and four selected application integrations, original-source pointer pilots and selected native/isolated parity tests; typed pools/scoped nonheap runtime tests on the experimental branch. Exact evidence is in [EVIDENCE_LEDGER.md](EVIDENCE_LEDGER.md).
2. **Resolved a real regression:** Nginx/PCRE8 previously lost original compiler diagnostic reasons/offsets; [PR #25](https://github.com/ARISTODE/interspec-typed-allocator/pull/25) fixed tested behavior with strict parity and four malformed U metadata rejection cases. This does not prove untested behavior.
3. **Partial:** 14 upstream application source expression candidates and selected native events are traceable to original source; these are not exhaustive, and **no demonstrated unchanged raw T stack address transit is established** by this pilot. Do not reuse adapter-observation totals as upstream prevalence.
4. **Hosted reference only:** 400 archived app samples over 12 workloads independently audited, plus prior microbenchmark/diagnostic evidence. This is not the final full controlled evaluation; the new typed pool/nonheap changes were not measured in those archived builds.
5. **Pending:** complete original source and boundary transit census, complete SP3 integration/negative and equivalence suites, controlled dedicated host performance, effective SP1/SP2/SP3 policy ablations, original paper row/PoC/coverage reconciliation, final manuscript rewrite.

Historic manuscript numbers (SP1 3,179/7,523; SP2+SP3 4,426/7,523; pointer coverage 1,955/1,966; reported geomean 7.5%) are **previous reported figures to independently revalidate**, not newly verified results for the current SP3 extension.

## Reading order and local workflow

1. Read `docs/NEXT_STEPS.md` and `docs/EVIDENCE_LEDGER.md`.
2. Check source and tests: `include/interspec/runtime.h`, `tests/runtime_object_layout.cpp`, `integration/`, `tools/source_origin/README.md` and the source provenance workflows.
3. Check the evidence requirements: `EVALUATION_COMPLETION.md`, `CONTROLLED_EVALUATION.md`, `evaluation/HOSTED_REFERENCE_AUDIT_20261102.md`, and draft PR #28's `CONTROLLED_GITHUB_CI.md`.
4. Confirm branch/PR/CI state. Preserve the exact upstream revisions, build manifests, diagnostics-off timing binaries, source hashes, original native outputs and artifacts.
5. Work through `docs/NEXT_STEPS.md`, updating status only when acceptance evidence exists.

## Ownership handoff

**Local Codex owns:** implementation, native original-source pointer origin/transit collection, behavior equivalence, security regressions, controlled evaluation collection and independent artifact verification.

**ChatGPT takes over later:** re-audit the completed [return handoff](RETURN_HANDOFF.md), reconcile experimental claims with manuscript code, present the writing plan to Jack, then update SP3 design, limitations, evaluation and tables in the private official paper after approval. A local Codex completion report is an input to review, not automatic proof of claims.
