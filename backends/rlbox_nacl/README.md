# InterSpec RLBox + NaCl backend

This directory packages the NaCl-specific mechanism required by the InterSpec runtime. It is intentionally separate from the generic `interspec::Runtime` policy logic.

## Supported upstream revisions

The exact supported revisions are recorded in `manifest.json`. `apply_backend.py` refuses to modify any other checkout, so backend behavior cannot silently drift with upstream changes.

## Backend contract

The patched RLBox backend exposes two small primitives to trusted code:

• `reserve_typed_arena(size)` reserves one U-readable/U-writable arena whose mapping is owned by T.
• `sandbox_address(ptr)` converts a host view of a sandbox pointer to its NaCl user address for trusted metadata lookup.

The trusted NaCl runtime records the reserved arena range and rejects untrusted `munmap`, `mprotect`, and `mmap(MAP_FIXED)` operations that overlap it. U can still read and write object bytes inside the arena; only T controls the mapping and allocation metadata.

## Applying the backend

After fetching the pinned `rlbox_nacl_sandbox` tree and synchronizing its `native_client` dependency, run:

```bash
python3 backends/rlbox_nacl/apply_backend.py --root /path/to/rlbox_nacl_sandbox
```

The E2E script performs exactly this operation and then builds the existing typed-allocation test. The remaining edits in that script are test-harness glue, not part of the security backend.
