# InterSpec Typed Allocator Research Preview

This release packages the completed P0 through P6 typed allocator proof of concept for extending InterSpec SP3 with trusted allocation metadata.

The release demonstrates:

• trusted TypeId to TypeHash registration owned by T

• tracked U allocations with trusted base, size, and type provenance

• expected type and allocation bounded pointer validation before T use

• logical lifetime invalidation across free and realloc

• precise source selected allocation instrumentation inferred by CodeQL

• a pinned RLBox + NaCl backend

• a complete rsync as T and real bundled popt as U application path

• P5 concurrency, arithmetic, collision, and scalability hardening

• P6 security evaluation, runtime microbenchmarks, reproducibility metadata, and an installable CMake package

The artifact is a research preview rather than a claim of production completeness. Address reuse is intentionally disabled because raw pointer reuse would require a separate temporal identity mechanism. The demonstrated real application coverage is the pinned rsync/popt path described in the repository documentation.

See `P6_EVALUATION.md`, `P6_RESULTS.md`, and `REPRODUCIBILITY.md` for evaluation scope, representative measurements, and exact reproduction commands.
