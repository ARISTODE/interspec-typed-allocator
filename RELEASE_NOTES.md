# InterSpec Typed Allocator Research Preview

This release packages the completed P0 through P7b typed allocator proof of concept for extending InterSpec SP3 with trusted allocation metadata.

The release demonstrates:

• trusted TypeId to TypeHash registration owned by T

• tracked U allocations with trusted base, size, type, and allocation-site provenance

• expected type and allocation-bounded pointer validation before T use

• logical lifetime invalidation across free and realloc

• precise source-selected allocation instrumentation inferred by CodeQL

• P7a allocation-site authority derived from trusted NaCl callback execution state rather than a TypeId selected by U

• P7b `interspec::PolicyRuntime` and composable boundary-policy generation, removing trusted type/site registration and callback-PC dispatch logic from application-specific bridges

• a pinned RLBox + NaCl backend

• a complete rsync as T and real bundled popt as U application path

• P5 concurrency, arithmetic, collision, and scalability hardening

• P6 security evaluation, runtime microbenchmarks, reproducibility metadata, and an installable CMake package

The artifact is a research preview rather than a claim of production completeness. P7b generalizes Extended SP3 policy/runtime integration, not arbitrary library API marshalling. Address reuse is intentionally disabled because raw pointer reuse would require a separate temporal identity mechanism. Allocation-site provenance is not general control-flow integrity, and U-controlled object contents remain untrusted. The demonstrated real application coverage is the pinned rsync/popt path described in the repository documentation.

See `P6_EVALUATION.md`, `P6_RESULTS.md`, `P7A_PROVENANCE.md`, `P7B_NATIVE_INTEGRATION.md`, and `REPRODUCIBILITY.md` for evaluation scope, provenance design, native integration details, representative measurements, and exact reproduction commands.
