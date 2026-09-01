# InterSpec Typed Allocator Research Preview

This release packages the Extended SP3 research prototype through P9c. The artifact strengthens InterSpec's pointer domain policy with trusted allocation metadata so covered trusted uses can require a live tracked allocation, the expected trusted type, and a byte extent contained within that allocation.

The release demonstrates:

1. trusted TypeId to TypeHash registration owned by T

2. tracked U allocations with trusted base, size, type, and allocation site provenance

3. expected type and allocation bounded pointer validation before T use

4. logical lifetime invalidation across free and realloc

5. precise source selected allocation instrumentation inferred by CodeQL

6. P7a allocation site authority derived from trusted NaCl callback execution state rather than a TypeId selected by U

7. P7b `interspec::PolicyRuntime` and composable boundary policy generation, removing trusted type and site registration and provenance dispatch logic from application specific bridges

8. P7c multi boundary generalization across rsync/popt, memcached/bipbuffer, PCRE name table metadata, and libyaml structured scalar output, including runtime sized interior pointer validation

9. P8 deterministic security, automation, performance, and packaging evidence with mechanically rendered paper facing summaries

10. P9a a three way rsync/popt reference measurement separating the RLBox only runtime path, typed allocation and provenance without final validation, and full Extended SP3 on the NaCl prototype backend

11. P9b a pinned RLBox wasm2c backend and complete rsync as T / real bundled popt as U path using wasm direct allocation site provenance

12. P9c a reproducible reconciliation against the final InterSpec paper's 32 SP3 pointer fields, including an explicit source reconstruction audit and release gating that prevents an unsupported exact Extended SP3 coverage percentage

P9b gives each authorized allocation site a unique direct Wasm import. The module supplies only the requested allocation size. The trusted host wrapper for that immutable import embeds the corresponding SiteId and dispatches to T's SiteId to TypeId policy. This avoids trusting a TypeId or SiteId selected by U while using a provenance primitive natural to wasm2c rather than NaCl callback program counters.

The P9b security smoke verifies valid tracked use together with spatial overflow, same domain untracked pointer, wrong type, and stale pointer rejection. The complete pinned rsync executable also runs its option parsing and local dry run workloads with the real bundled popt implementation inside RLBox wasm2c.

P9c reproduces the final paper denominator of 32 SP3 pointer fields exactly. The preserved final paper artifact does not contain a declared one row per paper field identity map for all 32 cases, while the preserved raw reports differ from the final table in granularity, cardinality, report version, or boundary coverage. P9c therefore completes in source fidelity limitation mode. It reports an exact case level eligible lower bound of 0 of 32 and an exact demonstrated lower bound of 0 of 32 only as provenance floors, not as estimates of mechanism applicability. Existing rsync/popt, memcached/bipbuffer, nginx/libpcre, and yaml/libyaml integrations remain valid mechanism evidence, but the release does not convert them into a guessed percentage of the paper's 32 fields.

P7c and P8 report inferred and explicit helper allocation sites separately. The memcached/bipbuffer allocation is a precise direct malloc site inferred from real source. PCRE and libyaml use allocator abstractions (`pcre_malloc` and `YAML_MALLOC`), so their selected object allocations are represented as explicit generated boundary helper sites rather than direct malloc inference.

The artifact remains a research preview rather than a claim of production completeness. Address reuse is intentionally disabled. Allocation site provenance is not general control flow integrity. U controlled object contents remain untrusted. The runtime does not prove intended object identity among multiple simultaneously live allocations of the same trusted type. Hosted CI timings are reproducibility references; final publication performance numbers require controlled hardware evaluation.

See `P6_EVALUATION.md`, `P7A_PROVENANCE.md`, `P7B_NATIVE_INTEGRATION.md`, `P7C_GENERALIZATION.md`, `P8_EVALUATION.md`, `P9A_EVALUATION.md`, `P9B_EVALUATION.md`, `P9C_EVALUATION.md`, and `REPRODUCIBILITY.md` for the detailed scope, design, evaluation, and reproduction commands.
