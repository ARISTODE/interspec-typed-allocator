# InterSpec Typed Allocator

Minimal proof-of-concept for extending InterSpec SP3 with trusted allocation metadata.

The PoC uses RLBox with the NaCl SFI backend. U may freely corrupt object bytes, while T keeps authoritative allocation metadata `{base, size, type_hash}` and validates U-controlled pointers before trusted use.

## Principles

• Keep the implementation small and readable.
• Reuse RLBox and NaCl mechanisms instead of rebuilding them.
• Separate trusted allocation metadata from untrusted object contents.
• Prefer a working end-to-end path over premature generality.

## Build the core check

```bash
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

## RLBox + NaCl PoC

```bash
./scripts/run_rlbox_nacl_poc.sh
```

The script fetches the RLBox NaCl backend and its modified NaCl compiler, adds the tiny PoC shim, builds the sandboxed module, and runs only the `[typed_allocator]` test.

The PoC checks:

• correct typed pointer → pass
• wrong allocated type → reject
• out-of-bounds access → reject
• freed pointer → reject
• untracked U allocation → reject
• valid interior pointer → pass
• interior pointer crossing the allocation end → reject

`Item` and `Other` intentionally have the same size, so the wrong-type case cannot be rejected by domain or size alone.

## Current scope

The first end-to-end milestone uses one RLBox sandbox allocation as the backing storage and keeps all sub-allocation metadata in T. This validates the callback, metadata, type, bounds, free, and untracked-pointer paths with minimal code.

The next milestone replaces that backing allocation with a trusted NaCl-reserved arena so arbitrary U cannot recycle the backing region through its normal allocator. Automatic Uriah type inference and InterSpec expected-use inference come after the runtime path is stable.
