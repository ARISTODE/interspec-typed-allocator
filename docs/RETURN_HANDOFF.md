# Local Codex → ChatGPT return handoff

**State:** TEMPLATE, NOT A COMPLETION REPORT. The local Codex agent must fill this file as work progresses and link the final PR before handing the project back for paper writing.

## 1. Exact source and review identity

* Implementation repository: https://github.com/ARISTODE/interspec-typed-allocator
* Starting branch / starting SHA: [fill]
* Final branch / final 40-character SHA: [fill]
* PR URL(s) and merge states: [fill]
* Official paper repository changes: **None unless separately approved**.
* Native upstream source revisions and configuration: [fill]

## 2. Task completion ledger

| Task | Status: Verified / Partial / Blocked | Main commit, CI run and artifact | Important exclusions |
| --- | --- | --- | --- |
| C0 GitHub/CI baseline | Pending | [fill] | [fill] |
| C1 Original source pointer census + actual transit | Pending | [fill] | [fill] |
| C2 Typed pools and stack/global SP3 deployment | Pending | [fill] | [fill] |
| C3 Native/isolation behavior and security regressions | Pending | [fill] | [fill] |
| C4 Controlled publication benchmarks | Pending | [fill] | [fill] |
| C5 Original paper claim/coverage reconciliation | Pending | [fill] | [fill] |

## 3. Pointer results (original source only)

For each boundary, provide a table or linked machine-readable artifact with:

1. Original source file:line, upstream commit, API/direction T→U or U→T, pointer role and storage category (stack, named global, static literal, heap, null, unknown).
2. Static unique sites versus dynamic native counts; sample workload/coverage.
3. Raw pointer actually passed across the isolation boundary versus copied bytes / handle / retained T outparam; T consumption and registered SP3 check.
4. Excluded InterSpec wrappers, generated adapters, test drivers, injected faults and host-only APIs.
5. Unknown/unresolved events explicitly retained, never added to heap counts.

Report exact figures and denominators here after independent verification: **[fill]**.

## 4. Implementation and correctness evidence

* New SP3 API usage in actual app bridges, with file:line evidence: [fill]
* Runtime tests (command, exit, expected denials): [fill]
* Four-mode normal behavior parity (workloads and observed outputs): [fill]
* Fault injection and negative test traces (T decision and before-use proof): [fill]
* Bugs found/fixed, and any remaining regression: [fill]
* Unsupported storage/type/lifetime cases and trust assumptions: [fill]

## 5. Performance and provenance

* Host ownership and dedicated hardware/topology, CPU placement, power settings: [fill]
* Build source SHAs, binary hashes and tools: [fill]
* Workloads, warmups, repetitions, raw sample count, failure count: [fill]
* CI run URLs, artifact names/IDs, SHA256 digests and retained archive location: [fill]
* Independent verifier command/results: [fill]
* Paired per-workload comparisons including confidence/variation: [fill]
* `publication_ready` decision: **false until independently reviewed**, reason: [fill].
* Missing runner/infrastructure or protocol deviations: [fill]

## 6. Paper implications and explicit open work

* SP3 original guarantee versus extended guarantee now justified: [fill]
* Claims/tables/figures that have verified support: [fill]
* Historic figures or boundaries still unverified: [fill]
* PCRE8 versus PCRE2 wording resolution: [fill]
* Recommended changes to SP3 design, security evaluation, performance evaluation, limitations and appendix: [fill]
* Tasks blocked, with exact requested action and owner: [fill]

## 7. Transfer gate

Before telling ChatGPT the work is ready, the local Codex agent must:

1. Ensure `docs/NEXT_STEPS.md` and `docs/EVIDENCE_LEDGER.md` match the exact evidence, including failures.
2. Link the GitHub PR/branch and immutable artifact URLs above.
3. State plainly which implementation and evaluation questions are **not finished**.
4. Ask ChatGPT to verify the evidence independently and propose manuscript edits for Jack's approval, rather than claiming that an experiment is publication ready merely because CI passed.
