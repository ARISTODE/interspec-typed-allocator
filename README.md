# InterSpec Typed Allocator

Minimal proof-of-concept for extending InterSpec SP3 with trusted allocation metadata.

The PoC uses RLBox with the NaCl SFI backend. U may freely corrupt object bytes, while T keeps authoritative allocation metadata `{base, size, type_hash}` and validates U-controlled pointers before trusted use.

## Principles

• Keep the implementation small and readable.
• Reuse RLBox, NaCl, and CodeQL mechanisms instead of rebuilding them.
• Separate trusted allocation metadata from untrusted object contents.
• Never accept a TypeHash as data supplied by U.
• Derive allocation instrumentation and T use checks from source-level analysis.
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

• U-side TypeIds are assigned automatically and selected ordinary `malloc` sites are rewritten to the InterSpec typed allocator.
• T-side `TypeId -> TypeHash` registration and expected `{type, offset, bytes}` access policies are generated from the same inferred input.
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

## RLBox + NaCl PoC

```bash
./scripts/run_rlbox_nacl_poc.sh
```

The script fetches the RLBox NaCl backend and its modified NaCl compiler, generates the P2 policy artifacts, adds the small InterSpec backend patch and PoC shim, builds the sandboxed module, and runs only the `[typed_allocator]` test.

The PoC checks:

• typed allocations create trusted metadata in T
• T registers the authoritative mapping `TypeId -> TypeHash`
• U may supply only a TypeId selector; an unknown TypeId is rejected
• choosing another registered TypeId gives that registered type and cannot forge or relabel the TypeHash
• ordinary U `malloc` does not create trusted metadata
• source-selected ordinary U `malloc` sites are automatically rewritten to tracked typed allocations
• T field uses consume inferred expected-type, byte-offset, and access-size policy
• the checked address returned to T is the same snapshot that passed validation
• correct typed pointer → pass
• wrong allocated type → reject
• out-of-bounds access → reject
• freed pointer → reject
• untracked U allocation → reject
• U cannot unmap, remap, or change protection on the trusted-managed arena

`Item` and `Other` intentionally have the same size, so the wrong-type case cannot be rejected by size alone.

## Current scope

T reserves one dedicated read/write arena inside U's NaCl address space. U can access object bytes, but T owns allocation metadata and the arena mapping. The PoC uses a bump allocator with no address reuse, so removing a metadata record makes stale pointers fail permanently during the test.

For type provenance, T registers a trusted policy table such as `1 -> H(Item)` and `2 -> H(Other)`. U's allocation request carries only the compact TypeId. The TypeId itself is not trusted: compromised U may choose any registered ID. The security property is that only T defines what each ID means. Stronger control-flow or allocation-site provenance is a separate future extension.

The runtime check is intentionally small: a pointer must belong to a tracked allocation, match the expected `TypeHash`, and keep the inferred requested access within that same allocation's bounds.
