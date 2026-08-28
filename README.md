# InterSpec Typed Allocator

Minimal proof-of-concept for extending InterSpec SP3 with trusted allocation metadata.

The PoC uses RLBox with the NaCl SFI backend. U may freely corrupt object bytes, while T keeps authoritative allocation metadata `{base, size, type_hash, site_id}` for provenance-aware allocations and validates U-controlled pointers before trusted use.

## Principles

• Keep the implementation small and readable.
• Reuse RLBox, NaCl, and CodeQL mechanisms instead of rebuilding them.
• Separate trusted allocation metadata from untrusted object contents.
• Never accept a TypeHash as data supplied by U.
• Derive allocation instrumentation and T use checks from source-level analysis.
• For precise source-derived policies, derive allocation type authority from the analyzed allocation instruction rather than a type selected by U.
• Keep generic InterSpec policy logic separate from NaCl-specific isolation mechanisms.
• Prefer a working end-to-end path over premature generality.

## Build the core check

```bash
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

The trusted runtime is exposed as the CMake target `interspec::runtime` and the public header `interspec/runtime.h`.

## P2b: source analysis to policy

`analysis/ql/policy_inference.ql` uses CodeQL to infer the policy facts needed by the runtime from source code:

• tracked U allocation sites and their allocated struct types, using the type operand of `sizeof(T)` at `malloc` calls
• T pointer-field uses, including the expected declaring type, field byte offset, and field byte size

`tools/codeql_policy_to_json.py` converts those query results into `policy/poc_policy.json`. CI regenerates the JSON and requires it to exactly match the checked-in snapshot, so the policy cannot silently drift away from the analyzed source.

The PoC query intentionally uses the known test boundary functions and a small trusted-use fixture. In a real InterSpec application, those selectors are replaced by InterSpec's existing boundary/data-flow analysis and actual trusted application source; the policy format and downstream runtime path stay the same.

## Generated policy and instrumentation

`tools/generate_policy.py` consumes the inferred policy and generates both sides of the enforcement contract:

• Precise source-located U allocation sites receive generated SiteIds, instruction labels, and site-authenticated allocation instrumentation. Older hand-written policies without source locations retain the TypeId request path only for backward compatibility.
• T-side type registration, allocation-site registration, and expected `{type, offset, bytes}` access policies are generated from the same inferred input.
• Generated checked accesses validate from the original object pointer through the end of the requested field access, then return the already-validated address/range for trusted use.

The resulting path is:

```text
U source + T source
        ↓
      CodeQL
        ↓
 inferred policy
        ↓
 policy generator
   ↙           ↘
U allocation   T checks
instrumentation
        ↘     ↙
   InterSpec runtime
        ↓
    RLBox + NaCl
```

## P3: versioned RLBox + NaCl backend

NaCl-specific enforcement is packaged under `backends/rlbox_nacl/` instead of being embedded in the PoC test script.

`manifest.json` pins the exact supported `rlbox_nacl_sandbox` and `nacl_sandbox_compiler` revisions. `apply_backend.py` verifies both revisions before making any changes, so an upstream update cannot silently change the security mechanism.

The backend exposes only the low-level primitives needed by the generic InterSpec runtime:

• reserve one T-managed, U-readable/U-writable arena in the NaCl address space
• convert a sandbox pointer to its NaCl user address for trusted metadata lookup
• reject U `munmap`, `mprotect`, and `mmap(MAP_FIXED)` operations that overlap the arena
• expose the trusted NaCl syscall return PC used by P7a allocation-site provenance

The generic allocation metadata, type policy, provenance policy, and bounds checks remain in `interspec::Runtime`; only the mechanism for obtaining the trusted U execution address is NaCl-specific.

## RLBox + NaCl PoC

```bash
./scripts/run_rlbox_nacl_poc.sh
```

The script fetches the pinned RLBox NaCl backend and modified NaCl compiler, applies the packaged InterSpec backend, generates the policy artifacts, adds only the PoC test-harness glue, builds the sandboxed module, and runs the `[typed_allocator]` test.

The PoC checks:

• source-selected ordinary U `malloc` sites are automatically rewritten to tracked allocations
• a precise analyzed allocation site determines the authoritative type without accepting a TypeId or SiteId from U
• the trusted NaCl syscall return PC must fall inside the registered allocation-site range
• invoking the allocator callback syscall from an unregistered U instruction is rejected
• allocating through an `Other` site and corrupting the bytes to look like `Item` does not relabel the trusted metadata
• legacy policies without source locations still support the older T-defined TypeId mapping, but do not receive the P7a site-provenance guarantee
• ordinary U `malloc` does not create trusted metadata
• T field uses consume inferred expected-type, byte-offset, and access-size policy
• the checked address returned to T is the same snapshot that passed validation
• correct typed pointer → pass
• wrong allocated type → reject
• out-of-bounds access → reject
• freed pointer → reject
• untracked U allocation → reject
• U cannot unmap, remap, or change protection on the trusted-managed arena

`Item` and `Other` intentionally have the same size, so the wrong-type case cannot be rejected by size alone.

## P4: real rsync popt boundary

P4 replaces the synthetic parser allocation sites with the bundled `popt` implementation from the pinned rsync source revision `7c20b077c980036a19587701cec320cc88e42a4a`.

`integration/rsync_popt/` contains the inferred policy, typed allocation lifetime shim, isolated RLBox test, and complete-rsync bridge. CodeQL derives the allocation policy from the real `popt/popt.c`; the generator instruments the selected allocation sites; and the isolated `[rsync_popt]` test executes that parser inside RLBox + NaCl.

The real-boundary test verifies that returned character pointers pass only when trusted metadata records a live allocation of the inferred character type. A pointer with the wrong tracked type is rejected as `wrong_type`, and an ordinary U allocation without trusted metadata is rejected as `untracked`.

## P4c: complete trusted rsync execution

P4c builds rsync 3.5.0 itself as T and interposes the context-dependent `popt` API with `integration/rsync_popt/p4c_bridge.cpp`. The parser implementation remains the real bundled `popt` code and executes inside the NaCl sandbox as U.

At the boundary, the bridge:

• copies trusted `argv`, option names, descriptions, and initial string values into U-owned memory
• reconstructs the `struct poptOption` table inside U rather than exposing T pointers to the parser
• creates U shadow storage for destination-backed option variables and copies validated results back to the corresponding T variables
• tracks typed allocation lifetime across allocation, free, and realloc operations so stale metadata is invalidated
• accepts returned U character pointers only after trusted type, liveness, spatial-bounds, and NUL-termination checks
• copies positional arguments back to T only after the same pointer validation

The CI path then executes the complete rsync binary with both option parsing and a normal local-transfer startup path:

```bash
rsync --backup-dir=<sandbox-test-dir> --max-size=1M --block-size=1024 --version
rsync --dry-run -a <src>/ <dst>/
```

The first invocation exercises option arguments, including a destination-backed string option. The second exercises positional arguments and the ordinary local-transfer path through rsync's real `main` and option-processing code. Both commands must return successfully for the `rlbox-nacl` CI job to pass.

The current P4c proof deliberately does not import host `popt` configuration files or aliases into U. It also does not claim exhaustive coverage of rsync daemon mode, remote-shell mode, authentication paths, or every optional feature. Its claim is narrower: the pinned complete rsync executable runs its ordinary CLI and local-transfer startup path while the context-dependent parser executes in RLBox + NaCl and U-returned pointers are mediated by trusted typed allocation metadata.

## P5: hardening and scalability

P5 keeps the P4c security model unchanged while removing assumptions that were acceptable for a small proof of concept but would not scale safely to larger policies or concurrent trusted callers.

The trusted runtime now uses an ordered allocation map. A containing allocation is found with `upper_bound`, making pointer lookup logarithmic in the number of live tracked allocations rather than a linear scan. Type bindings use hash maps. Runtime metadata is protected by a shared mutex: checks and metadata reads take shared access, while registration, allocation, release, and reallocation take exclusive access.

P5 also makes metadata arithmetic fail closed. Arena construction detects address-space wraparound. Allocation alignment and `base + used` calculations are overflow checked. Generated trusted accesses reject `offset + bytes` overflow. Type registration rejects both duplicate TypeIds and duplicate TypeHashes, so a generated TypeHash collision cannot silently create two trusted meanings for the same runtime value.

Allocation instrumentation is now tied to the exact source location inferred by CodeQL. The policy records the analyzed `malloc` source span. The generator starts from that analyzed call and preserves its original size expression, so it can instrument one selected allocation even when a function contains multiple `malloc` calls or the allocation size is an arbitrary expression. The older function-pattern path remains only for backward compatibility with hand-written policies that do not carry source locations.

P5 deliberately retains a bump arena with no physical address reuse. Release and successful reallocation remove the old authoritative metadata, but the allocator never immediately assigns that numerical address to a new object. This prevents an old raw pointer from becoming valid again merely because a later same-type allocation reused the address. Reclaiming addresses safely would require an additional temporal identity mechanism such as tagged or generation-aware pointers, so address reuse is outside the current model rather than being treated as a harmless optimization.

The hardening tests include:

• invalid arena and integer-overflow cases
• exact-base release semantics
• successful and failed realloc semantics, including keeping the old object live when reallocation fails
• TypeHash collision rejection
• a 10,000-allocation metadata stress test
• concurrent allocation, checking, size lookup, and release from eight trusted threads
• precise source-site instrumentation when multiple `malloc` calls appear in one function
• the full P4c rsync + RLBox + NaCl regression, ensuring the hardening changes preserve the real application path

## P6: evaluation and research preview

P6 turns the completed mechanism into an evaluated and reproducible artifact without expanding its security claim.

`evaluation/security_eval.cpp` provides a machine-readable security matrix covering expected type checks, spatial bounds, untracked pointers, exact-base release, stale pointers after free and realloc, realloc failure semantics, TypeHash collision rejection, unknown TypeIds, zero-sized allocations, and invalid arena handling.

`evaluation/runtime_bench.cpp` reports lookup and allocation costs as CSV while sweeping from 1 to 16,384 live allocations. It also reports read-only check throughput with 1, 2, 4, and 8 trusted threads. Timing is intentionally not a CI pass threshold because hosted runner performance is noisy; correctness remains independently enforced by tests.

Run the reproducible evaluation with:

```bash
bash scripts/run_p6_evaluation.sh
```

The detailed methodology is in `P6_EVALUATION.md`, one representative CI result is recorded in `P6_RESULTS.md`, and exact reproduction steps are in `REPRODUCIBILITY.md`.

The runtime is now installable as a CMake package. A clean external project can use `find_package(interspec-runtime CONFIG REQUIRED)` and link `interspec::runtime`. CI verifies this path with `examples/consumer/`.

A research preview archive can be built with:

```bash
bash scripts/package_release.sh
```

The default artifact is `interspec-typed-allocator-0.1.0.tar.gz` with a SHA256 checksum. The package contains the installed public runtime interface, CMake package metadata, evaluation and reproducibility documentation, representative results, the P7a provenance documentation, and the pinned RLBox + NaCl manifest.

## P7a: allocation-site provenance

P7a closes the remaining TypeId-selection weakness for precise source-derived allocation policies.

CodeQL identifies an allocation instruction and its inferred object type. The generator emits trusted begin/end symbols around that exact allocation expression and replaces the allocation with a direct NaCl callback syscall. NaCl captures the syscall's sandbox return address into trusted per-thread state before the host callback executes. T resolves the generated site symbols, matches the trusted return PC against the registered site range, and only then creates allocation metadata with the site's authoritative type.

The precise path is therefore:

```text
analyzed allocation instruction
        ↓
generated site range
        ↓
U executes direct allocator syscall
        ↓
trusted NaCl return PC
        ↓
T site lookup
        ↓
{base, size, type_hash, site_id}
```

A compromised U that knows the allocator callback slot cannot obtain trusted metadata by invoking that callback syscall from arbitrary code, because the trusted return PC is outside every authorized site. Likewise, U may overwrite an object allocated by the `Other` site so that its bytes resemble `Item`, but the authoritative metadata remains `Other` and an `Item` use fails with `wrong_type`.

The real rsync/popt path uses the same mechanism for the CodeQL-derived `poptGetContext` and `expandNextArg` sites and for the explicitly registered typed string-copy site. The complete P4c rsync regression remains part of the acceptance test.

Detailed design and limitations are documented in `P7A_PROVENANCE.md`.

## Current scope

T reserves one dedicated read/write arena inside U's NaCl address space. U can access object bytes, but T owns allocation metadata and the arena mapping. The allocator intentionally does not reuse released addresses, so removing a metadata record makes stale pointers fail permanently for the lifetime of the arena.

For precise source-derived allocation policies, T no longer trusts U to select a type. T registers each analyzed allocation instruction as a trusted site range bound to an inferred type. A tracked allocation is created only when the trusted NaCl syscall return PC identifies one of those authorized sites. The resulting metadata records the site's `site_id` and `type_hash` together with the allocation base and size.

Legacy hand-written policies that do not carry allocation source locations retain the older `TypeId -> TypeHash` request path for backward compatibility. Compromised U may choose among registered TypeIds on that legacy path, so those allocations do not receive the P7a allocation-site provenance guarantee.

P7a is allocation-site provenance, not control-flow integrity. If compromised U legitimately reaches an authorized allocation instruction, the allocation receives that site's type. U also remains free to corrupt bytes within its writable objects. T therefore still validates liveness, expected type, and spatial bounds before consuming a U-controlled pointer.
