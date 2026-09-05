# InterSpec Typed Allocator

Research proof of concept for extending InterSpec SP3 with trusted allocation metadata and allocation-site provenance.

The implementation supports RLBox with both the NaCl SFI prototype backend and the wasm2c backend used by the InterSpec evaluation family. U may corrupt object bytes, while T owns authoritative allocation metadata `{base, size, type_hash, site_id}` and validates U-controlled pointers before trusted use.

## Principles

• Keep trusted allocation metadata separate from U-controlled object contents.
• Never accept a TypeHash as data supplied by U.
• Derive allocation instrumentation and T-side use checks from source analysis.
• For precise source-derived policy, derive allocation type authority from the analyzed allocation instruction rather than a TypeId selected by U.
• Keep generic InterSpec policy/runtime logic separate from backend-specific isolation mechanisms.
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

`tools/generate_policy.py` instruments precise source-selected U allocations and generates T-side type/site/use policy. `tools/generate_boundary_policy.py` composes that source-derived policy with explicitly declared boundary helper sites. P7c also supports runtime-sized uses through generated `checked_dynamic_access()` checks. `tools/generate_wasm_boundary_policy.py` emits the equivalent policy for the wasm2c backend using unique direct Wasm imports as trusted allocation-site identities.

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

NaCl-specific enforcement is packaged under `backends/rlbox_nacl/`. The backend reserves the T-managed arena, protects its mapping, converts sandbox addresses, and exposes trusted callback execution state. P7a binds precise source-derived allocation sites to trusted NaCl callback return PCs.

The wasm2c backend is packaged under `backends/rlbox_wasm2c/`. P9b and P10 use a provenance primitive natural to Wasm: each authorized allocation site receives a unique direct import, and the trusted host wrapper embeds the corresponding SiteId. U supplies only the requested allocation size and cannot select a TypeId or SiteId as ordinary data.

Type policy, allocation-site policy, liveness, and spatial checks remain in the generic runtime for both backends.

## Real rsync / popt baseline

The baseline real integration uses bundled `popt` from pinned rsync revision `7c20b077c980036a19587701cec320cc88e42a4a`.

CodeQL derives the real `poptGetContext` and `expandNextArg` allocation sites. The isolated test rejects a tracked wrong type and an untracked same-domain U pointer. The complete trusted rsync path interposes context-dependent popt APIs while the real bundled parser executes inside RLBox.

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

`evaluation/security_eval.cpp` provides a machine-readable security matrix. `evaluation/runtime_bench.cpp` measures runtime costs over allocation-count and thread-count sweeps. The installable CMake package is validated by `examples/consumer/`.

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

P7c validates the same P7b mechanism on three additional real boundaries selected to exercise different pointer shapes:

• `memcached/bipbuffer`: a direct source-derived `bipbuf_new()` allocation and an interior `bipbuf_peek_all()` pointer validated with a runtime byte extent.

• `nginx/libpcre`: PCRE1 8.45 compiled-pattern metadata where the name table is an interior pointer into the compiled object. PCRE's configurable `pcre_malloc` abstraction is represented explicitly as a generated boundary helper site.

• `yaml/libyaml`: a U-owned structured `yaml_event_t` whose nested scalar value pointer and runtime length are returned to T and validated before copying. `YAML_MALLOC` is represented explicitly as a generated boundary helper site.

All three run in the combined RLBox + NaCl test module together with the synthetic provenance tests and rsync/popt baseline. Each new boundary exercises valid behavior and rejects tracked wrong-type memory, untracked same-domain memory, and corrupted runtime extents where applicable.

`integration/p7c_manifest.json` and `tools/p7c_report.py` are the machine-readable generalization record. Detailed acceptance criteria and limitations are in `P7C_GENERALIZATION.md`.

## P8 and P9 evaluation finalization

P8 turns the mechanism into a reproducible research artifact with deterministic security and automation reporting, trusted-metadata microbenchmarks, paired real-boundary measurements, and mechanically rendered paper-facing summaries.

P9a adds a true RLBox-only runtime-path baseline for rsync/popt so the runtime cost can be separated into trusted allocation/provenance tracking, final validation, and total Extended-SP3 overhead.

P9b ports the rsync/popt Extended-SP3 path to RLBox wasm2c. It uses unique direct Wasm imports for allocation-site authority and verifies valid use, spatial overflow rejection, same-domain untracked-pointer rejection, wrong-type rejection, and stale-pointer rejection.

## P10 wasm2c multi-boundary generalization

P10 ports all three P7c generalization boundaries to the same wasm2c backend used by P9b:

• `memcached/bipbuffer` preserves its precise source-derived allocation site and runtime-sized interior pointer validation.
• `nginx/libpcre` preserves the explicit compiled-regex helper site and validates the returned name-table range.
• `yaml/libyaml` preserves the explicit scalar-value helper site and validates the nested scalar range before trusted use.

Each boundary executes its valid path and rejects wrong-type tracked memory, untracked same-domain memory, and corrupted extents. The dedicated P10 CI driver is `scripts/run_p7c_wasm2c.sh`, and the completed design and reproduction path are documented in `P10_WASM2C_P7C.md`.

```bash
bash scripts/run_p7c_wasm2c.sh
```

## Current security scope

T reserves a dedicated read/write region inside U's sandbox address space. U can access object bytes, but T owns the authoritative allocation metadata. Before trusted pointer consumption, T validates liveness, expected type, and spatial extent.

For precise source-derived policy, U does not select the authoritative allocation type. Explicit helper allocation sites are trusted boundary policy and receive the same site-authenticated runtime metadata path.

The mechanism does not prove arbitrary parser-output integrity, general control-flow integrity, or temporal identity under physical address reuse. U-controlled object contents remain untrusted. It also does not prove intended-object identity among multiple simultaneously live allocations of the same trusted type; a check establishes containment in a live allocation of the expected trusted type and requested bounds. Arbitrary library ABI marshalling remains application-specific.