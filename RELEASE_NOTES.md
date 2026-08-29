# InterSpec Typed Allocator Research Preview

This release packages the completed P0 through P7c typed allocator proof of concept for extending InterSpec SP3 with trusted allocation metadata.

The release demonstrates:

• trusted TypeId to TypeHash registration owned by T

• tracked U allocations with trusted base, size, type, and allocation-site provenance

• expected type and allocation-bounded pointer validation before T use

• logical lifetime invalidation across free and realloc

• precise source-selected allocation instrumentation inferred by CodeQL

• P7a allocation-site authority derived from trusted NaCl callback execution state rather than a TypeId selected by U

• P7b `interspec::PolicyRuntime` and composable boundary-policy generation, removing trusted type/site registration and callback-PC dispatch logic from application-specific bridges

• P7c multi-boundary generalization across rsync/popt, memcached/bipbuffer, PCRE name-table metadata, and libyaml structured scalar output, including runtime-sized interior-pointer validation

• boundary-global helper-site symbols namespaced by generated policy so multiple policies can coexist in one NaCl module

• a pinned RLBox + NaCl backend and complete rsync-as-T / real bundled popt-as-U application path

• P5 concurrency, arithmetic, collision, and scalability hardening

• P6 security evaluation, runtime microbenchmarks, reproducibility metadata, and an installable CMake package

P7c reports inferred and explicit helper allocation sites separately. The memcached/bipbuffer allocation is a precise direct-malloc site inferred from real source. PCRE and libyaml use allocator abstractions (`pcre_malloc` and `YAML_MALLOC`), so their selected object allocations are represented honestly as explicit generated boundary helper sites rather than as direct-malloc inference.

The artifact remains a research preview rather than a claim of production completeness. P7c generalizes Extended-SP3 security-policy/runtime integration, not arbitrary library API marshalling. Address reuse is intentionally disabled. Allocation-site provenance is not general control-flow integrity, U-controlled object contents remain untrusted, and the runtime does not prove intended-object identity among multiple simultaneously live allocations of the same trusted type.

See `P6_EVALUATION.md`, `P6_RESULTS.md`, `P7A_PROVENANCE.md`, `P7B_NATIVE_INTEGRATION.md`, `P7C_GENERALIZATION.md`, `P7C_RESULTS.md`, and `REPRODUCIBILITY.md` for the detailed scope, design, evaluation, and reproduction commands.
