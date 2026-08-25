# InterSpec Typed Allocator

Minimal proof-of-concept for extending InterSpec SP3 with trusted allocation metadata.

The PoC uses RLBox with the NaCl SFI backend. U may freely corrupt object bytes, while T keeps authoritative allocation metadata `{base, size, type_hash}` and validates U-controlled pointers before trusted use.

## Principles

• Keep the implementation small and readable.
• Reuse RLBox and NaCl mechanisms instead of rebuilding them.
• Separate trusted allocation metadata from untrusted object contents.
• Do not accept the allocation type as data supplied by U.
• Prefer a working end-to-end path over premature generality.

## Build the core check

```bash
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

The trusted runtime is exposed as the CMake target `interspec::runtime` and the public header `interspec/runtime.h`.

## RLBox + NaCl PoC

```bash
./scripts/run_rlbox_nacl_poc.sh
```

The script fetches the RLBox NaCl backend and its modified NaCl compiler, adds the small InterSpec backend patch and PoC shim, builds the sandboxed module, and runs only the `[typed_allocator]` test.

The PoC checks:

• typed allocations create trusted metadata in T
• allocation TypeHash is selected by a T-side allocation entry point, not supplied by U
• U can call the wrong typed entry point, but the resulting allocation keeps that entry point's trusted type label
• ordinary U `malloc` does not create trusted metadata
• correct typed pointer → pass
• wrong allocated type → reject
• out-of-bounds access → reject
• freed pointer → reject
• untracked U allocation → reject
• valid interior pointer → pass
• interior pointer crossing the allocation end → reject
• U cannot unmap, remap, or change protection on the trusted-managed arena

`Item` and `Other` intentionally have the same size, so the wrong-type case cannot be rejected by size alone.

## Current scope

T reserves one dedicated read/write arena inside U's NaCl address space. U can access object bytes, but T owns allocation metadata and the arena mapping. The PoC uses a bump allocator with no address reuse, so removing a metadata record makes stale pointers fail permanently during the test.

For type provenance, the current PoC registers separate trusted allocation callbacks for `Item` and `Other`. U passes only an allocation size. The TypeHash is fixed by the T-side callback, so U cannot inject an arbitrary TypeHash or relabel an existing allocation. Production integration will generate these trusted bindings from statically inferred allocation sites/types rather than hand-writing them.

The runtime check is intentionally small: a pointer must belong to a tracked allocation, match the expected `TypeHash`, and keep the requested access within that allocation's bounds. Automatic allocation-site binding and InterSpec expected-use inference are the next integration steps.
