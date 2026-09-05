# InterSpec Typed Allocator Research Preview

This release packages the Extended-SP3 research prototype through P10. The artifact strengthens InterSpec's pointer-domain policy with trusted allocation metadata so covered trusted uses can require a live tracked allocation, the expected trusted type, and a byte extent contained within that allocation.

The release demonstrates:

• trusted TypeId to TypeHash registration owned by T

• tracked U allocations with trusted base, size, type, and allocation-site provenance

• expected-type and allocation-bounded pointer validation before T use

• logical lifetime invalidation across free and realloc

• precise source-selected allocation instrumentation inferred by CodeQL

• P7a allocation-site authority derived from trusted NaCl callback execution state rather than a TypeId selected by U

• P7b `interspec::PolicyRuntime` and composable boundary-policy generation, removing trusted type/site registration and provenance dispatch logic from application-specific bridges

• P7c multi-boundary generalization across rsync/popt, memcached/bipbuffer, PCRE name-table metadata, and libyaml structured scalar output, including runtime-sized interior-pointer validation

• P8 deterministic security, automation, performance, and packaging evidence with mechanically rendered paper-facing summaries

• P9a a three-way rsync/popt reference measurement separating the RLBox-only runtime path, typed allocation/provenance without final validation, and full Extended SP3 on the NaCl prototype backend

• P9b a pinned RLBox wasm2c backend and complete rsync-as-T / real bundled popt-as-U path using wasm-direct allocation-site provenance

• P10 wasm2c generalization of the three P7c boundaries: memcached/bipbuffer, nginx/libpcre, and yaml/libyaml

P9b and P10 give each authorized allocation site a unique direct Wasm import. The module supplies only the requested allocation size. The trusted host wrapper for that immutable import embeds the corresponding SiteId and dispatches to T's SiteId-to-TypeId policy. This avoids trusting a TypeId or SiteId selected by U while using a provenance primitive natural to wasm2c rather than NaCl callback program counters.

The P9b security smoke verifies valid tracked use together with spatial-overflow, same-domain untracked-pointer, wrong-type, and stale-pointer rejection. The complete pinned rsync executable also runs its option-parsing and local dry-run workloads with the real bundled popt implementation inside RLBox wasm2c.

P10 reuses the same wasm2c runtime and provenance mechanism for three additional real boundaries. The combined P10 smoke verifies the valid trusted-use path for each boundary and rejects tracked wrong-type memory, ordinary same-domain untracked memory, and corrupted runtime extents. The successful CI run reports that all three P7c generalization boundaries pass on wasm2c.

P7c/P8/P10 report inferred and explicit helper allocation sites separately. The memcached/bipbuffer allocation is a precise direct-malloc site inferred from real source. PCRE and libyaml use allocator abstractions (`pcre_malloc` and `YAML_MALLOC`), so their selected object allocations are represented as explicit generated boundary helper sites rather than direct-malloc inference.

The artifact remains a research preview rather than a claim of production completeness. Address reuse is intentionally disabled. Allocation-site provenance is not general control-flow integrity. U-controlled object contents remain untrusted. The runtime does not prove intended-object identity among multiple simultaneously live allocations of the same trusted type. Hosted CI timings are reproducibility references; final publication performance numbers require controlled-hardware evaluation.

See `P6_EVALUATION.md`, `P7A_PROVENANCE.md`, `P7B_NATIVE_INTEGRATION.md`, `P7C_GENERALIZATION.md`, `P8_EVALUATION.md`, `P9A_EVALUATION.md`, `P9B_EVALUATION.md`, `P10_WASM2C_P7C.md`, and `REPRODUCIBILITY.md` for the detailed scope, design, evaluation, and reproduction commands.