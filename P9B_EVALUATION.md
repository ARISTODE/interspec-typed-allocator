# P9b wasm2c Integration

P9b moves Extended SP3 from the Native Client prototype backend to RLBox's wasm2c backend so the strengthened pointer policy can be evaluated with the same isolation family used by the InterSpec paper.

P9b does not add a stronger security property than P8. Its purpose is backend equivalence and a paper-compatible execution path.

## 1. Security goal

For a covered U allocation site, compromised U must not be able to select the trusted allocation type by supplying a TypeId or allocation-site identifier as ordinary data. T must derive the allocation's type from a trusted identity associated with the analyzed source site.

The wasm2c path therefore uses a different provenance primitive from P7a's NaCl syscall return program counter.

```text
CodeQL allocation site
        ↓
source span + inferred type
        ↓
unique direct Wasm import at that source instruction
        ↓
immutable Wasm direct-call target
        ↓
trusted host import wrapper with embedded SiteId
        ↓
T SiteId → TypeId binding
        ↓
trusted {base, size, type_hash, site_id}
```

The allocation call carries only the requested size. It does not carry a TypeId or SiteId chosen by U.

## 2. Why direct Wasm imports are the provenance primitive

A Wasm module cannot rewrite its own validated code. A direct `call` instruction names a fixed function import in the module. InterSpec gives each authorized source allocation site a unique imported allocation function. The corresponding trusted host wrapper embeds that site's SiteId and forwards it to the trusted runtime.

This provides the same policy-level invariant as P7a while using the execution primitive naturally provided by wasm2c. A compromised U execution may still reach an authorized allocation instruction through unintended control flow. Preventing that requires control-flow integrity and remains outside Extended SP3, matching the limitation already stated for P7a.

P9b deliberately does not use a generic imported allocator that accepts `site_id` or `type_id` as an argument because U could replay such values.

## 3. Typed memory in Wasm linear memory

At sandbox initialization T reserves one large block through the module's ordinary allocator. The Wasm allocator therefore treats the complete block as live and does not reuse it for ordinary U allocations. T manages suballocations inside that block with `interspec::Runtime` and records their trusted liveness, type hash, and site identifier.

Allocation imports return 32-bit offsets inside this reserved Wasm block. U can read and write the object bytes normally, but it cannot modify T's metadata. Logical free removes the trusted allocation record. Reallocation creates a new tracked suballocation while preserving trusted type and site metadata.

## 4. Boundary helper allocations

Explicit boundary-helper sites remain distinct from source-derived sites. In the wasm2c backend, a helper site receives its own direct import identity and trusted SiteId. This preserves P8's reporting distinction while avoiding a U-selected type argument.

## 5. Initial P9b boundary

The first end-to-end target is the existing rsync/popt boundary because it already has two source-derived allocation sites, one explicit typed string helper site, a complete trusted application bridge, and P8/P9a security and performance evidence.

The pinned policy contains two precise source sites: `expandNextArg` producing `char` and `poptGetContext` producing `poptContext_s`. The explicit `popt_typed_strdup` helper is the third trusted allocation site.

## 6. Completion criteria

P9b is complete when CI demonstrates that:

1. the existing NaCl policy generation and P7/P8/P9a regressions remain unchanged and green,
2. wasm-direct generation emits a unique direct import for every precise and helper allocation site,
3. no wasm allocation import accepts TypeId or SiteId from U,
4. the trusted wasm host wrappers embed the site identifiers used for runtime metadata,
5. a pinned RLBox wasm2c sandbox can reserve the typed region and translate trusted-use pointers to Wasm offsets,
6. real pinned rsync/popt executes through RLBox wasm2c with typed allocation, lifetime tracking, and final Extended-SP3 liveness/type/spatial validation enabled, and
7. at least one adversarial same-domain wrong-type or untracked-pointer case is rejected on the wasm2c path before P9b is merged.

Performance thresholds are not completion gates. Publication-quality timing remains a later controlled-hardware step.

## 7. Pinned upstream basis

The P9b backend manifest pins the upstream RLBox API, `rlbox_wasm2c_sandbox`, WABT/wasm2c, and wasi-sdk generation used by CI. Pinning is required because the upstream wasm2c sandbox currently tracks moving `main` branches for some build dependencies.
