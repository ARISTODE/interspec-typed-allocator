# InterSpec Typed Allocator Research Preview

This release packages the completed P0 through P8 typed allocator proof of concept for extending InterSpec SP3 with trusted allocation metadata.

The release demonstrates:

• trusted TypeId to TypeHash registration owned by T;

• tracked U allocations with trusted base, size, type, and allocation-site provenance;

• expected type and allocation-bounded pointer validation before T use;

• logical lifetime invalidation across free and realloc;

• precise source-selected allocation instrumentation inferred by CodeQL;

• P7a allocation-site authority derived from trusted NaCl callback execution state rather than a TypeId selected by U;

• P7b `interspec::PolicyRuntime` and composable boundary-policy generation, removing trusted type/site registration and callback-PC dispatch logic from application-specific bridges;

• P7c multi-boundary generalization across rsync/popt, memcached/bipbuffer, PCRE name-table metadata, and libyaml structured scalar output, including runtime-sized interior-pointer validation;

• boundary-global helper-site symbols namespaced by generated policy so multiple policies can coexist in one NaCl module;

• P8 paper-facing security, automation/generalization, repeated primitive-cost, and reproducibility outputs generated from one machine-readable evaluation contract;

• a pinned RLBox + NaCl backend and complete rsync-as-T / real bundled popt-as-U application path;

• P5 concurrency, arithmetic, collision, and scalability hardening; and

• an installable CMake research-preview package.

P8 refines the evaluation accounting. Attack-only helper sites are not counted as integration effort. Production allocation policy across the four evaluated boundaries currently contains three source-derived allocation sites and three explicit integration helper sites. The PCRE and libyaml allocations are explicit because their real source paths go through allocator abstractions (`pcre_malloc` and `YAML_MALLOC`) rather than the direct-malloc pattern handled by the source transformer.

Trusted-use evidence is also labeled explicitly. The rsync/popt use is derived from real application source. The memcached/bipbuffer, PCRE, and libyaml P7c trusted-use policies are representative analysis adapters used to exercise different pointer shapes; the release does not describe those three adapters as automatic inference from the original trusted applications.

P8 pairs an original-SP3-style U-domain/range check with the Extended-SP3 live-allocation/type/object-bound check for the same pointer and extent. Runtime measurements are repeated and aggregated by median, while every raw repetition and environment description is retained. Hosted CI values are regression/reference data, not a universal performance claim; controlled paper measurements should use the dedicated-machine procedure in `REPRODUCIBILITY.md`.

The artifact remains a research preview rather than a claim of production completeness. Extended SP3 is not general control-flow integrity, U-controlled object contents remain untrusted, physical address reuse is intentionally disabled, intended-object identity among simultaneously live same-type allocations is not proven, and arbitrary library ABI marshalling remains application-specific.

See `P6_EVALUATION.md`, `P6_RESULTS.md`, `P7A_PROVENANCE.md`, `P7B_NATIVE_INTEGRATION.md`, `P7C_GENERALIZATION.md`, `P7C_RESULTS.md`, `P8_EVALUATION.md`, and `REPRODUCIBILITY.md` for the detailed scope, design, evaluation, and reproduction commands.
