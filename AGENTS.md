# InterSpec contributor and Codex instructions

This repository contains experimental security research. Treat source code, CI runs, raw artifacts and pinned upstream revisions as evidence; prior summaries and comments are not substitutes for checking them.

## Mandatory startup

1. Read [the Codex handoff](docs/CODEX_HANDOFF.md), [the evidence ledger](docs/EVIDENCE_LEDGER.md), [the task ledger](docs/NEXT_STEPS.md), and [the return handoff](docs/RETURN_HANDOFF.md).
2. Read `CONTROLLED_EVALUATION.md`, `EVALUATION_COMPLETION.md`, `docs/SP3_TYPED_POOL_NONHEAP.md`, `tools/source_origin/README.md`, and relevant reproducibility documentation before touching a benchmark.
3. Inspect actual checkout HEAD, git status, open PRs, source changes, and relevant CI statuses. The experimental SP3 branch differs from `main`; do not assume every PR is merged into the main branch.
4. Present a brief evidence-backed status and plan before substantial implementation or manuscript changes. Preserve unrelated uncommitted work.

## Nonnegotiable scientific and security constraints

1. The original-source pointer census counts ONLY pointer expressions/events attributed to pinned upstream application/library source in the declared scope. Exclude InterSpec bridges, wrappers, generated glue, fault injection, harness code, and project-authored YAML drivers from original-application prevalence. Separately report static candidate sites, native execution events, actual T/U pointer transit, and trusted dereferences. Unknown origins remain unknown. A pointer copied into a sandbox allocation does not mean the original address crossed a boundary.
2. T is trusted; U may be compromised inside an RLBox sandbox. Never trust U-provided type, site, length, lifetime or domain authority. SP3 checks must use trusted metadata and independently determined expected types. Failing to find a matching record fails closed; ordinary heap checks do not silently accept nonheap pointers.
3. Typed struct pools, field interior accesses, and scoped external stack/global/T-heap registrations require exact trusted layout and lifetime metadata. Generic U stack support requires authenticated compiler/backend lifetime information. Runtime unit tests do NOT imply all real application bridges use these APIs.
4. Report separately: compile success, unit tests, real application execution, behavioral parity, injected corruption rejection, profiling, hosted performance and controlled publication measurements. No invented/favorable-only measurements. A green CI build is not publication evidence.
5. For performance, follow `CONTROLLED_EVALUATION.md` and independently validate raw files and source/binary hashes. GitHub-hosted reference timings are not a controlled publication run; avoid cross-host geometric means. Keep diagnostic builds out of timing samples.
6. Preserve normal application behavior and security boundaries. Test native, RLBox-only, tracking-only and Extended-SP3 modes using matched inputs; report observed scope and any differences.
7. Do NOT change the private official paper repository `ARISTODE/Automatic-Access-Policy-Enforcement` until the user approves a paper revision plan backed by completed evidence. Reconcile PCRE8 experiment versus PCRE2 manuscript language and historical SP1/SP2/SP3 metrics first.

## Finish and return protocol

At the end of each meaningful milestone, update `docs/NEXT_STEPS.md` with its actual status and evidence links; add or correct `docs/EVIDENCE_LEDGER.md` without overwriting old runs. Before returning work to ChatGPT, complete `docs/RETURN_HANDOFF.md` with exact commit SHAs, PRs, CI run links, artifact names/hashes, commands, results, remaining failures, and paper-claim implications. Open a reviewable PR; do not silently merge scientific claims. If a required dedicated host or trust mechanism is unavailable, mark that task blocked rather than claiming it completed.
