# SP3 typed pools and nonheap pointer policy

## Scope and trusted metadata

The SP3 runtime retains a trusted table in T memory. Compiler and interface metadata, never untrusted U data, defines type hashes, exact object size, alignment, field offsets, domains and lifetime registration tokens. A pointer without a matching trusted record is rejected.

The existing `Runtime::check` continues to cover registered heap allocation byte ranges. It is not silently broadened to accept stack or global addresses.

## Array and structure pools

`register_type_layout` defines the true element stride `sizeof(T)` and alignment `alignof(T)`. `allocate_typed_array` records the element count with the managed allocation and aligns its base using arithmetic that supports nonpower-of-two strides. `check_typed_element` computes the element index and offset with division and remainder, and accepts only the beginning of a complete element and an access contained within that one element.

An interior pointer such as `&array[i].field` is permitted only if trusted code registers the corresponding field type, offset, extent and optional interior-byte policy. `check_typed_field` checks those descriptors without rounding an arbitrary pointer to a guessed allocation base. Overlapping descriptors, including ambiguous unions, are rejected by default. The optional trusted `expected_element_base` argument prevents substitution of a different same-type element within a pool when the interface has an established original object identity.

Existing untyped byte buffers retain their prior range semantics. Typed array checks deliberately fail closed for allocations lacking an explicit layout.

## Stack and global objects

The observed original application sites do not require raw T stack addresses to enter U. In deployed benchmark paths, T stack buffers are copied into registered sandbox storage; Nginx's original U static PCRE8 diagnostic is staged inside a tracked U allocation and copied into T-owned stable text. The original native outparameters remain in T. These are boundary marshaling guarantees, not evidence that raw nonheap addresses are accepted.

For a future interface that explicitly permits a nonheap pointer, T code can register a trusted `register_nonheap_array` record with domain, type, extent, and storage class. The returned token binds checks to one registration lifetime. `unregister_nonheap` revokes it; an old token remains invalid even if an object is later registered at the same address. The nonheap APIs require both a trusted token and the expected domain; no ordinary heap check starts accepting raw stack or global pointers.

A U-controlled callback must **never** be allowed to forge the type, size, lifetime token, or registration site. U stack registration is safe only if a trusted compiler/backend provides authentic scope and lifetime information. Without that instrumentation, U stack pointers remain untracked and are rejected. This is an explicit trust requirement, not a solved generic case.

## Validation and claim boundaries

`tests/runtime_object_layout.cpp` exercises nonpower-of-two element stride and alignment, field interior and exact start, same-type element substitution, cross-element accesses, oversized or overlapping registrations, malformed reallocations, T stack and U global domain checks, copy-based T/U transfer, revocation and address reuse. The cases are **runtime tests**, not claims of deployment-wide instrumentation.

Outstanding integration work includes type descriptor generation at all relevant interfaces, site-authorized registration in every real backend, scope instrumentation where raw U stack pointers are required, and benchmarking of the new layout-aware checks. `void*`, ambiguous unions, flexible array members, unsized/opaque types, and unobserved boundaries must not be counted as covered without explicit interface annotations or additional inference.

The selected source-only provenance study excludes project wrappers and deliberate fault injections. It establishes observed application pointer origins and exercised marshaling paths, **not** an exhaustive denominator of all reachable pointers.
