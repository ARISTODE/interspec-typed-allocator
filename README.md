# InterSpec Typed Allocator

Research proof of concept for extending InterSpec SP3 with trusted allocation metadata and allocation-site provenance.

The implementation uses RLBox with the NaCl SFI backend. U may corrupt object bytes, while T owns authoritative allocation metadata `{base, size, type_hash, site_id}` and validates U-controlled pointers before trusted use.

## Principles

• Keep trusted allocation metadata separate from U-controlled object contents.
• Never accept a TypeHash as data supplied by U.
• Derive allocation instrumentation and T-side use checks from source analysis.
• For precise source-derived policy, derive allocation type authority from the analyzed allocation instruction rather than a TypeId selected by U.
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

`analysis/ql/` contains CodeQL queries that infer the policy facts needed by the runtime. For the synthetic and rsync/popt paths this includes:

• U allocation sites and inferred object types
• exact source locations for precise allocation instructions
• T pointer uses, including expected type, byte offset, and access size

`tools/codeql_policy_to_json.py` converts query results into policy JSON. CI regenerates checked-in policy snapshots and requires them to match, preventing silent drift between analysis and enforcement.

`tools/generate_policy.py` converts source-derived policy into both sides of the enforcement contract:

• precise U allocation sites receive SiteIds, exported instruction labels, and site-authenticated allocation instrumentation
• T receives type registration, allocation-site registration, and expected `{type, offset, bytes}` access policy
• generated checked accesses validate the whole requested extent before returning the trusted-use address

The core path is:

```text
U source + T source
        ↓
      CodeQL
        ↓
 inferred policy
        ↓
 policy generation
   ↙           ↘
U allocation   T access policy
instrumentation
        ↘     ↙
 InterSpec policy/runtime
        ↓
    RLBox + NaCl
```

## Versioned RLBox + NaCl backend

NaCl-specific enforcement is packaged under `backends/rlbox_nacl/`.

`manifest.json` pins the supported `rlbox_nacl_sandbox` and `nacl_sandbox_compiler` revisions. `apply_backend.py` verifies those revisions before applying the InterSpec backend changes.

The backend exposes the low-level mechanisms needed by the generic runtime:

• reserve one T-managed, U-readable/U-writable arena inside the NaCl address space
• convert a host-visible sandbox pointer to its NaCl user address
• prevent U from unmapping, remapping, or changing protection on the typed arena
• expose trusted callback execution state used to authenticate precise allocation instructions

Allocation metadata, type policy, site policy, liveness, and spatial checks remain in the generic InterSpec runtime.

## RLBox + NaCl end-to-end test

```bash
./scripts/run_rlbox_nacl_poc.sh
```

The script fetches the pinned backend, applies the packaged modifications, generates synthetic and rsync/popt policy artifacts, builds the NaCl module, runs adversarial tests, and finally builds and executes the complete rsync path.

The synthetic provenance test checks:

• precise source-selected `malloc` sites become tracked allocations
• allocation type is determined by the authorized site rather than U-supplied TypeId data
• invoking the allocator callback from an unregistered U instruction is rejected
• allocating from an `Other` site and rewriting bytes to look like `Item` does not change trusted metadata
• ordinary U allocation without trusted metadata is rejected as `untracked`
• wrong allocated type is rejected as `wrong_type`
• out-of-bounds and stale pointers are rejected
• the typed arena cannot be unmapped, remapped, or reprotected by U

`Item` and `Other` intentionally have the same size, so type confusion cannot be rejected by size alone.

## Real rsync / popt boundary

The real integration uses the bundled `popt` implementation from pinned rsync source revision `7c20b077c980036a19587701cec320cc88e42a4a`.

CodeQL derives the real allocation policy from `popt/popt.c`, including `poptGetContext` and `expandNextArg`. The isolated `[rsync_popt]` test executes the real parser inside RLBox + NaCl and verifies that:

• a valid live `char` allocation is accepted
• a tracked pointer with the wrong type is rejected
• a normal same-domain U allocation with no trusted metadata is rejected

## Complete trusted rsync execution

`integration/rsync_popt/p4c_bridge.cpp` interposes the context-dependent `popt` API while rsync itself remains T and the real bundled parser executes as U.

The bridge still performs application-specific marshalling:

• copies trusted argv, option names, descriptions, and initial strings into U memory
• reconstructs the `poptOption` table in U rather than exposing T pointers
• creates U shadow storage for destination-backed option variables
• synchronizes scalar and string results back to T
• validates U-returned character pointers for liveness, expected type, spatial bounds, and NUL termination before copying strings to T
• retrieves positional arguments element by element so T never dereferences a U `char**`

The complete rsync acceptance path executes:

```bash
rsync --backup-dir=<sandbox-test-dir> --max-size=1M --block-size=1024 --version
rsync --dry-run -a <src>/ <dst>/
```

The claim is deliberately narrow: the pinned complete rsync executable runs its ordinary CLI and local-transfer startup path with context-dependent popt parsing inside RLBox + NaCl. The proof does not import host popt configuration/aliases and does not claim exhaustive daemon, remote-shell, authentication, or optional-feature coverage.

## P5 hardening and scalability

The trusted runtime uses an ordered allocation map for logarithmic containing-allocation lookup, hash maps for type bindings, and a shared mutex for concurrent trusted readers/writers.

Hardening includes:

• checked arena and allocation arithmetic
• exact-base release semantics
• failed realloc preserving the old live allocation
• successful realloc preserving type and site provenance while invalidating old metadata
• TypeHash collision rejection
• concurrent runtime tests
• metadata stress tests with 10,000 live allocations
• precise source-site instrumentation when multiple `malloc` calls occur in one function

The current arena intentionally does not reuse released numerical addresses. Removing metadata therefore makes stale raw pointers permanently invalid for the lifetime of that arena. Safe reuse would require an additional temporal identity mechanism.

## P6 evaluation and research preview

`evaluation/security_eval.cpp` emits a machine-readable security matrix covering expected type, spatial bounds, untracked pointers, release/realloc semantics, stale pointers, collisions, unknown TypeIds, zero-sized allocations, and invalid arenas.

`evaluation/runtime_bench.cpp` measures lookup/allocation cost while sweeping from 1 to 16,384 live allocations and reports read-only check throughput across multiple trusted threads. Timing is reported rather than used as a CI threshold.

Run the evaluation with:

```bash
bash scripts/run_p6_evaluation.sh
```

The runtime is installable as a CMake package and is validated by `examples/consumer/`.

A research preview archive can be built with:

```bash
bash scripts/package_release.sh
```

The package includes the installed runtime headers, CMake metadata, evaluation/reproducibility documentation, P7a provenance documentation, P7b native-integration documentation, and the pinned RLBox + NaCl manifest.

## P7a allocation-site provenance

P7a closes the TypeId-selection weakness for precise source-derived allocation policies.

CodeQL identifies an allocation instruction and its inferred object type. The generator emits trusted begin/end symbols around the exact allocation instruction and replaces it with a direct NaCl allocator callback syscall. NaCl captures trusted callback execution state before host dispatch. T resolves generated site symbols, matches the trusted callback return PC to an authorized site range, and derives the authoritative type from that site.

```text
analyzed allocation instruction
        ↓
generated site range
        ↓
U executes allocator syscall
        ↓
trusted NaCl callback PC
        ↓
T site lookup
        ↓
{base, size, type_hash, site_id}
```

A compromised U that knows the callback slot cannot create trusted metadata from an arbitrary instruction. U may still legitimately execute an authorized allocation instruction and may corrupt the resulting object bytes, so P7a is allocation-site provenance rather than general control-flow integrity.

Detailed design and limitations are in `P7A_PROVENANCE.md`.

## P7b native InterSpec policy/runtime integration

P7b removes trusted allocation-policy plumbing from application-specific bridges.

`interspec::PolicyRuntime` now owns the generic binding between generated policy and a sandbox backend. It centralizes:

• generated type registration
• generated allocation-site symbol resolution and registration
• callback-PC provenance dispatch into `Runtime::allocate_from_pc()`

`tools/generate_boundary_policy.py` composes the source-derived policy with boundary-specific helper-site declarations. A helper allocation needed for API marshalling can therefore be represented as policy data and emitted into the same U/T policy pair rather than maintained as a second trusted registration table.

For rsync/popt, `integration/rsync_popt/boundary.json` declares the typed string-copy helper as a `char` allocation site. The old hand-maintained `site_provenance.h` path is removed. The generated policy exposes one `register_allocation_policy()` entry point that registers both CodeQL-derived sites and helper sites.

The synthetic provenance test and the complete rsync/popt bridge both use `PolicyRuntime`. The remaining rsync bridge code is application-specific marshalling rather than Extended SP3 type/site registration or callback provenance logic.

P7b does **not** claim automatic generation of arbitrary library ABI marshalling. A new boundary can still require code for complex tables, callbacks, or output slots. What is reusable is the Extended SP3 analysis → generated policy → trusted runtime → sandbox-backend enforcement path.

Detailed design and acceptance criteria are in `P7B_NATIVE_INTEGRATION.md`.

## Current security scope

T reserves a dedicated read/write arena inside U's NaCl address space. U can access object bytes, but T owns the arena mapping and allocation metadata.

For precise source-derived policy, T does not trust U to select allocation type. Tracked metadata is created only when trusted callback execution state identifies an authorized allocation site. T then checks liveness, expected type, and spatial extent before consuming a U-controlled pointer.

Legacy hand-written policies without precise source locations retain the older T-defined `TypeId -> TypeHash` request path for backward compatibility and therefore do not receive the P7a provenance guarantee.

The mechanism does not prove arbitrary parser-output integrity, control-flow integrity, or temporal identity under physical address reuse. U-controlled object contents remain untrusted, and application-specific scalar output policies remain separate from this Extended SP3 pointer-safety work.
