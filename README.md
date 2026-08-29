# InterSpec Typed Allocator

Research proof of concept for extending InterSpec SP3 with trusted allocation metadata and allocation-site provenance.

The implementation uses RLBox with the NaCl SFI backend. U may corrupt object bytes, while T owns authoritative allocation metadata `{base, size, type_hash, site_id}` and validates U-controlled pointers before trusted use.

## Principles

• Keep trusted allocation metadata separate from U-controlled object contents.
• Never accept a TypeHash as data supplied by U.
• Derive allocation instrumentation and T-side use checks from source analysis where the source pattern is supported.
• For precise source-derived policy, derive allocation type authority from the analyzed allocation instruction rather than a TypeId selected by U.
• Represent unsupported allocator abstractions as explicit trusted boundary policy instead of labeling them automatic.
• Keep generic InterSpec policy/runtime logic separate from NaCl-specific isolation mechanisms.
• Keep application-specific API marshalling separate from Extended SP3 enforcement.

## Build the core runtime

```bash
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

The installable CMake target is `interspec::runtime`. The public runtime interfaces are `interspec/runtime.h` and `interspec/policy_runtime.h`.

## Source analysis and generated policy

`analysis/ql/` contains CodeQL queries that infer allocation and trusted-use facts. `tools/codeql_policy_to_json.py` converts query results into policy JSON, and CI requires checked-in policy snapshots to match regenerated results.

`tools/generate_policy.py` instruments precise source-selected U allocations and generates T-side type/site/use policy. `tools/generate_boundary_policy.py` composes that source-derived policy with explicitly declared boundary helper sites and runtime-sized access policy.

```text
U source + T source
        ↓
      CodeQL
        ↓
 inferred policy
        ↓
 boundary policy generation
   ↙                 ↘
U allocation sites   T expected uses
        ↘             ↙
        PolicyRuntime
             ↓
     trusted metadata
             ↓
        RLBox + NaCl
```

## Versioned RLBox + NaCl backend

NaCl-specific enforcement is packaged under `backends/rlbox_nacl/`. The manifest pins supported backend/compiler revisions. The backend reserves the T-managed arena, protects its mapping, converts sandbox addresses, and exposes trusted callback execution state. Type policy, allocation-site policy, liveness, and spatial checks remain in the generic runtime.

## Real rsync / popt baseline

The baseline real integration uses bundled `popt` from pinned rsync revision `7c20b077c980036a19587701cec320cc88e42a4a`.

CodeQL derives the real `poptGetContext` and `expandNextArg` allocation sites and a trusted pointer use from real `rsync/options.c`. The isolated test rejects a tracked wrong type and an untracked same-domain U pointer. The complete trusted rsync path interposes context-dependent popt APIs while the real bundled parser executes in NaCl.

The complete rsync acceptance path executes:

```bash
rsync --backup-dir=<sandbox-test-dir> --max-size=1M --block-size=1024 --version
rsync --dry-run -a <src>/ <dst>/
```

The claim is deliberately narrow: ordinary CLI and local-transfer startup for the pinned rsync build. Host popt configuration/aliases are not imported, and exhaustive daemon, remote-shell, authentication, or optional-feature coverage is not claimed.

## P5 hardening and scalability

The trusted runtime uses logarithmic containing-allocation lookup, hash maps for type bindings, and shared locking for concurrent T readers/writers. Hardening covers checked arithmetic, exact-base lifetime operations, realloc semantics, TypeHash collision rejection, concurrency, metadata stress, and precise instrumentation with multiple malloc calls.

Released numerical addresses are not reused. Safe physical reuse would require an additional temporal identity mechanism.

## P6 evaluation and research preview

`evaluation/security_eval.cpp` provides a machine-readable security matrix. `evaluation/runtime_bench.cpp` sweeps allocation counts and trusted-reader thread counts. The installable CMake package is validated by `examples/consumer/`.

```bash
bash scripts/run_p6_evaluation.sh
bash scripts/package_release.sh
```

## P7a allocation-site provenance

P7a binds precise source-derived allocations to the trusted NaCl callback return PC. The analyzed allocation instruction determines the authoritative type; U cannot obtain trusted metadata by invoking the allocator callback from an arbitrary instruction.

```text
analyzed allocation instruction
        ↓
generated site range
        ↓
trusted callback return PC
        ↓
T site lookup
        ↓
{base, size, type_hash, site_id}
```

This is allocation-site provenance, not general control-flow integrity. Detailed design is in `P7A_PROVENANCE.md`.

## P7b native policy/runtime integration

P7b introduces `interspec::PolicyRuntime` and composable boundary-policy generation so application bridges no longer duplicate trusted type/site registration or callback-PC dispatch. Boundary-specific API marshalling remains separate from the Extended-SP3 security mechanism. Detailed design is in `P7B_NATIVE_INTEGRATION.md`.

## P7c multi-boundary generalization

P7c validates the same P7b mechanism on three additional real library boundaries selected to exercise different pointer shapes:

• `memcached/bipbuffer`: a direct source-derived `bipbuf_new()` allocation and an interior `bipbuf_peek_all()` pointer validated with a runtime byte extent.

• `nginx/libpcre` pattern: PCRE1 8.45 compiled-pattern metadata where the name table is an interior pointer into the compiled object. PCRE's configurable `pcre_malloc` abstraction is represented explicitly as a generated boundary helper site.

• `yaml/libyaml`: a U-owned structured `yaml_event_t` whose nested scalar value pointer and runtime length are returned to T and validated before copying. `YAML_MALLOC` is represented explicitly as a generated boundary helper site.

All three run in the combined RLBox + NaCl test module together with the synthetic provenance tests and rsync/popt baseline. Each new boundary exercises valid behavior and rejects tracked wrong-type memory, untracked same-domain memory, and corrupted runtime extents where applicable.

P7c also fixes a generalization issue discovered by the multi-policy test: helper-site assembly labels are namespaced by generated policy, so multiple boundaries can safely use the same local helper name/SiteId in one NaCl module.

The P7c trusted-use adapters for memcached, PCRE, and libyaml are representative T-side consumption shapes used to test enforcement generality. They are not claimed as automatic inference from those applications' original trusted source. `integration/p7c_manifest.json` records that evidence provenance explicitly.

Detailed acceptance criteria and limitations are in `P7C_GENERALIZATION.md` and `P7C_RESULTS.md`.

## P8 paper-quality evaluation

P8 converts the implementation into one reproducible evidence package organized around four research questions: security effectiveness, automation/generalization, incremental enforcement cost, and claim/reproducibility boundaries.

The evaluation deliberately separates three things that are easy to conflate:

1. **Security mechanism evidence.** Runtime edge cases come from `evaluation/security_eval.cpp`; real-boundary attack evidence is emitted only after the combined RLBox + NaCl tests pass.

2. **Automation evidence.** Source-derived allocation sites, explicit integration helper sites, and attack-only helper sites are counted separately. Trusted-use facts are labeled `real_application_source` or `analysis_adapter`.

3. **Performance evidence.** `evaluation/runtime_bench.cpp` now pairs an original-SP3-style domain/range baseline with Extended SP3 for the same pointer/extent. The Extended check adds live allocation lookup, expected type, and containing-object bounds. Repeated runs are aggregated by median; every raw repetition is preserved.

At the current four boundaries, production allocation policy contains three source-derived allocation sites and three explicit integration helper sites. Three additional helper sites exist only to construct adversarial wrong-type tests and are excluded from integration effort. Of the four trusted-use policies, rsync/popt is derived from real application source; the three P7c generalization uses are explicitly labeled analysis adapters.

Run the lightweight P8 pipeline with:

```bash
INTERSPEC_P8_REPETITIONS=5 \
INTERSPEC_BENCH_ITERATIONS=200000 \
./scripts/run_p8_evaluation.sh p8-results
```

To require fresh RLBox + NaCl boundary evidence in a compatible environment:

```bash
INTERSPEC_P8_RUN_RLBOX=1 \
INTERSPEC_P8_REQUIRE_BOUNDARY_EVIDENCE=1 \
./scripts/run_p8_evaluation.sh p8-results
```

CI performs the expensive RLBox test once, uploads its boundary-security evidence, and makes the downstream `paper-evaluation` job require that evidence. The paper-facing outputs are `automation.csv`, `security-runtime.csv`, `security-boundaries.csv`, `runtime-overhead.csv`, `summary.json`, and generated `summary.md`, alongside every raw runtime repetition and environment metadata.

P8 does not turn shared hosted-runner timing into a universal performance claim. Controlled paper measurements should be collected on a dedicated machine using the procedure in `REPRODUCIBILITY.md`.

Detailed methodology and acceptance criteria are in `P8_EVALUATION.md`.

## Current security scope

T reserves a dedicated read/write arena inside U's NaCl address space. U can access object bytes, but T owns the arena mapping and authoritative allocation metadata. Before trusted pointer consumption, T validates liveness, expected type, and spatial extent.

For precise source-derived policy, U does not select the authoritative allocation type. Explicit integration helper allocation sites are trusted boundary policy and receive the same site-authenticated runtime metadata path.

The mechanism does not prove arbitrary parser-output integrity, general control-flow integrity, or temporal identity under physical address reuse. U-controlled object contents remain untrusted. It also does not prove intended-object identity among multiple simultaneously live allocations of the same trusted type; a check establishes containment in a live allocation of the expected trusted type and requested bounds. Arbitrary library ABI marshalling remains application-specific.
