# InterSpec Typed Allocator

Minimal proof-of-concept for extending InterSpec SP3 with trusted allocation metadata.

The PoC uses RLBox with the NaCl SFI backend. U may freely corrupt object bytes, while T keeps authoritative allocation metadata `{base, size, type_hash}` and validates U-controlled pointers before trusted use.

## Principles

• Keep the implementation small and readable.
• Reuse RLBox and NaCl mechanisms instead of rebuilding them.
• Separate trusted allocation metadata from untrusted object contents.
• Never accept a TypeHash as data supplied by U.
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
• T registers the authoritative mapping `TypeId -> TypeHash`
• U may supply only a TypeId selector; an unknown TypeId is rejected
• choosing another registered TypeId gives that registered type and cannot forge or relabel the TypeHash
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

For type provenance, T first registers a trusted policy table such as `1 -> H(Item)` and `2 -> H(Other)`. U's allocation request carries only the compact TypeId. The runtime resolves that untrusted selector against the trusted table before creating metadata, so U cannot inject an arbitrary TypeHash. If U changes the selector from `Item` to the registered `Other` ID, the resulting allocation is still recorded as `Other` and fails a later `Item` check. Unknown IDs allocate nothing.

Production integration will generate the TypeId assignments and T-side policy table from statically inferred allocation types. Stronger control-flow or allocation-site provenance is a separate future extension; it is not required for the current allocation-type guarantee.

The runtime check is intentionally small: a pointer must belong to a tracked allocation, match the expected `TypeHash`, and keep the requested access within that allocation's bounds. Automatic allocation instrumentation and InterSpec expected-use inference are the next integration steps.
