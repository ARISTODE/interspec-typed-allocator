# InterSpec Typed Allocator

Research proof of concept for extending InterSpec SP3 with trusted allocation metadata and allocation site provenance.

The implementation has end to end evidence with RLBox using both NaCl SFI and wasm2c. U may corrupt object bytes, while T owns authoritative allocation metadata `{base, size, type_hash, site_id}` and validates U controlled pointers before trusted use.

## Principles

1. Keep trusted allocation metadata separate from U controlled object contents.

2. Never accept a TypeHash as data supplied by U.

3. Derive allocation instrumentation and T side use checks from source analysis.

4. For precise source derived policy, derive allocation type authority from the analyzed allocation instruction rather than a TypeId selected by U.

5. Keep generic InterSpec policy and runtime logic separate from backend specific isolation mechanisms.

6. Keep application specific API marshalling separate from Extended SP3 enforcement.

## Build the core runtime

```bash
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

The installable CMake target is `interspec::runtime`. The public runtime interfaces are `interspec/runtime.h` and `interspec/policy_runtime.h`.

## Source analysis and generated policy

`analysis/ql/` contains CodeQL queries that infer allocation and trusted use facts. `tools/codeql_policy_to_json.py` converts query results into policy JSON, and CI requires checked in policy snapshots to match regenerated results.

`tools/generate_policy.py` instruments precise source selected U allocations and generates T side type, site, and use policy. `tools/generate_boundary_policy.py` composes that source derived policy with explicitly declared boundary helper sites. P7c also supports runtime sized uses through generated `checked_dynamic_access()` checks.

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
       RLBox backend
```

## Versioned RLBox backends

NaCl specific enforcement is packaged under `backends/rlbox_nacl/`. The manifest pins supported backend and compiler revisions. The backend reserves the T managed allocation region, protects its mapping, converts sandbox addresses, and exposes trusted callback execution state. Type policy, allocation site policy, liveness, and spatial checks remain in the generic runtime.

P9b adds `backends/rlbox_wasm2c/`. Its manifest pins RLBox, wasm2c sandbox, and WABT revisions. The wasm2c backend uses distinct direct Wasm imports for authorized allocation sites so the trusted import wrapper, rather than U supplied ordinary data, determines the SiteId and corresponding TypeId.

## Real rsync / popt baseline

The baseline real integration uses bundled `popt` from pinned rsync revision `7c20b077c980036a19587701cec320cc88e42a4a`.

CodeQL derives the real `poptGetContext` and `expandNextArg` allocation sites. The isolated test rejects a tracked wrong type and an untracked same domain U pointer. The complete trusted rsync path interposes context dependent popt APIs while the real bundled parser executes inside the sandbox.

The complete rsync acceptance path executes:

```bash
rsync --backup-dir=<sandbox-test-dir> --max-size=1M --block-size=1024 --version
rsync --dry-run -a <src>/ <dst>/
```

The claim is deliberately narrow: ordinary CLI and local transfer startup for the pinned rsync build. Host popt configuration and aliases are not imported, and exhaustive daemon, remote shell, authentication, or optional feature coverage is not claimed.

## P5 hardening and scalability

The trusted runtime uses logarithmic containing allocation lookup, hash maps for type bindings, and shared locking for concurrent T readers and writers. Hardening covers checked arithmetic, exact base lifetime operations, realloc semantics, TypeHash collision rejection, concurrency, metadata stress, and precise instrumentation with multiple malloc calls.

Released numerical addresses are not reused. Safe physical reuse would require an additional temporal identity mechanism.

## P6 evaluation

`evaluation/security_eval.cpp` provides a machine readable security matrix. `evaluation/runtime_bench.cpp` measures trusted metadata costs over allocation count and thread count sweeps. The installable CMake package is validated by `examples/consumer/`.

```bash
bash scripts/run_p6_evaluation.sh p6-results
```

## P7a allocation site provenance

P7a binds precise source derived allocations to the trusted NaCl callback return PC. The analyzed allocation instruction determines the authoritative type; U cannot obtain trusted metadata by invoking the allocator callback from an arbitrary instruction.

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

This is allocation site provenance, not general control flow integrity. Detailed design is in `P7A_PROVENANCE.md`.

## P7b native policy and runtime integration

P7b introduces `interspec::PolicyRuntime` and composable boundary policy generation so application bridges no longer duplicate trusted type and site registration or provenance dispatch. Boundary specific API marshalling remains separate from the Extended SP3 security mechanism. Detailed design is in `P7B_NATIVE_INTEGRATION.md`.

## P7c multi boundary generalization

P7c validates the same P7b mechanism on three additional real boundaries selected to exercise different pointer shapes.

1. `memcached/bipbuffer` uses a direct source derived `bipbuf_new()` allocation and an interior `bipbuf_peek_all()` pointer validated with a runtime byte extent.

2. `nginx/libpcre` uses PCRE1 8.45 compiled pattern metadata where the name table is an interior pointer into the compiled object. PCRE's configurable `pcre_malloc` abstraction is represented explicitly as a generated boundary helper site.

3. `yaml/libyaml` uses a U owned structured `yaml_event_t` whose nested scalar value pointer and runtime length are returned to T and validated before copying. `YAML_MALLOC` is represented explicitly as a generated boundary helper site.

All three run in the combined RLBox + NaCl test module together with the synthetic provenance tests and rsync/popt baseline. Each new boundary exercises valid behavior and rejects tracked wrong type memory, untracked same domain memory, and corrupted runtime extents where applicable.

`integration/p7c_manifest.json` and `tools/p7c_report.py` are the machine readable generalization record. CI runs the report with `--require-complete`. Detailed acceptance criteria and limitations are in `P7C_GENERALIZATION.md` and `P7C_RESULTS.md`.

## P8 paper quality evaluation

P8 turns the P0 through P7c mechanism into a reproducible research artifact. It combines the P6 security matrix, trusted metadata runtime measurements, exact regeneration of checked in real boundary policy snapshots, P7c generalization status, paired real boundary validation measurements, paired rsync measurements, environment evidence, and release packaging checks.

```bash
INTERSPEC_BENCH_ITERATIONS=100000 \
./scripts/run_p8_evaluation.sh p8-results

INTERSPEC_P8_BOUNDARY_ITERATIONS=20000 \
INTERSPEC_P8_APP_REPETITIONS=9 \
./scripts/run_p8_rlbox_evaluation.sh p8-rlbox-results
```

The P8 boundary performance baseline is `tracked_no_check`. It keeps sandboxing, typed allocation and provenance, policy registration, and marshalling enabled while bypassing only the final Extended SP3 acceptance check. Reported paired percentages therefore measure incremental final validation cost, not total Extended SP3 cost versus plain RLBox.

Hosted runner timings are reproducibility references. Final publication timing numbers should be rerun on controlled hardware.

## P9a RLBox only baseline

P9a adds a three way rsync/popt reference measurement with `rlbox_only`, `tracked_no_check`, and `extended_sp3`. This separates typed allocation and provenance cost from the final pointer validation cost on the NaCl prototype path.

```bash
INTERSPEC_P9A_APP_REPETITIONS=9 \
./scripts/collect_p9a_rlbox_results.sh p9a-rlbox-results
```

P9a is a reference measurement rather than a replacement for controlled hardware publication timing.

## P9b RLBox wasm2c integration

P9b demonstrates that Extended SP3 is not tied to NaCl return program counters. It ports trusted allocation provenance to the RLBox wasm2c backend used by the InterSpec evaluation.

```bash
./scripts/run_rlbox_wasm2c_poc.sh
```

Each authorized allocation site is rewritten to a distinct direct Wasm import. U supplies only the requested allocation size. The trusted host wrapper embeds the SiteId and dispatches through T's SiteId to TypeId policy. The security smoke checks valid tracked use plus spatial overflow, untracked same domain pointer, wrong type, and stale pointer rejection. The driver also builds a complete rsync as T executable with real bundled popt executing as U inside RLBox wasm2c and runs option parsing plus a local dry run.

Detailed scope is in `P9B_EVALUATION.md`.

## P9c final paper SP3 coverage reconciliation

P9c asks whether the Extended SP3 prototype can be given an exact applicability percentage over the 32 pointer fields protected by SP3 in the final InterSpec paper.

```bash
./scripts/run_p9c_evaluation.sh p9c-results
```

The evaluator reproduces the final denominator exactly: 32 SP3 pointer fields across 10 boundaries. It then audits the preserved final paper artifact for an exact one row per paper field identity map. The artifact preserves aggregate paper counts, but the raw analysis reports are not consistently aligned with those final units in cardinality, granularity, report version, or boundary coverage.

P9c therefore completes in source fidelity limitation mode. `p9c-report.json` has `p9c_evaluation_complete=true` while `capability_resolution_complete=false` and `source_fidelity_complete=false`. It deliberately reports no exact Extended SP3 percentage over the 32 fields. The exact eligible and exact demonstrated lower bounds are currently 0 of 32 as provenance floors only, not estimates of mechanism applicability.

Existing rsync/popt, memcached/bipbuffer, nginx/libpcre, and yaml/libyaml integrations remain valid mechanism evidence. P9c prevents those demonstrations from being silently converted into a stronger paper coverage claim than the preserved evidence supports.

Detailed methodology and limitations are in `P9C_EVALUATION.md` and the generated `P9C_RESULTS.md` artifact.

## Build the complete research preview

The release archive requires P8 deterministic evidence, P8 RLBox evidence, and P9c coverage reconciliation evidence.

```bash
./scripts/run_p8_evaluation.sh p8-results
./scripts/run_p8_rlbox_evaluation.sh p8-rlbox-results
./scripts/run_p9c_evaluation.sh p9c-results

INTERSPEC_P8_EVAL_DIR="$PWD/p8-results" \
INTERSPEC_P8_RLBOX_DIR="$PWD/p8-rlbox-results" \
INTERSPEC_P9C_EVAL_DIR="$PWD/p9c-results" \
./scripts/package_release.sh dist
```

The package script rejects incomplete P8 deterministic evidence, incomplete P9c reconciliation, or a P9c paper denominator other than 32. See `REPRODUCIBILITY.md` for the pinned dependencies and full reproduction sequence.

## Current security scope

T owns authoritative allocation metadata and validates liveness, expected type, and spatial extent before trusted pointer consumption. For precise source derived policy, U does not select the authoritative allocation type. Explicit helper allocation sites are trusted boundary policy and receive the same site authenticated runtime metadata path.

The mechanism does not prove arbitrary parser output integrity, general control flow integrity, or temporal identity under physical address reuse. U controlled object contents remain untrusted. It also does not prove intended object identity among multiple simultaneously live allocations of the same trusted type. A check establishes containment in a live allocation of the expected trusted type and requested bounds. Arbitrary library ABI marshalling remains application specific.
