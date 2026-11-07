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

For a future interface that explicitly permits a pointer to a T heap pool, stack object, or U static object, T code can register a trusted `register_external_array` record (or the nonheap-specific alias `register_nonheap_array`) with domain, type, extent, and storage class. The returned token binds checks to one registration lifetime. `unregister_external` (or `unregister_nonheap`) revokes it; an old token remains invalid even if an object is later registered at the same address. The nonheap APIs require both a trusted token and the expected domain; no ordinary heap check starts accepting raw stack or global pointers.

For APIs returning a raw address rather than a registration token,
`check_external_element_by_address` and `check_external_field_by_address`
search trusted metadata in T and enforce domain, type, element extent, and
optional field checks. They reject untracked or revoked objects, but cannot
disambiguate address reuse (ABA) after a new same-type registration, or prove
intended-object identity without a trusted expected base. Token-bound checks
remain the stronger temporal identity mechanism.

The opt-in memcached H2 comparator registers each raw `item*` in T at its
trusted LRU enqueue site, validates before item use, and revokes the consumed
queue reference. The default integration still uses one-use handles. In the
injected `item* + 1` case, domain-only validation accepted the pointer and T
raised AddressSanitizer, while both Extended SP3 and the one-use handle
rejected the corruption. The check generalizes that protection; it is not
stronger than the existing handle. See
[`../SP3_SECURITY_DELTA_RESULTS.md`](../SP3_SECURITY_DELTA_RESULTS.md).

A U-controlled callback must **never** be allowed to forge the type, size, lifetime token, or registration site. U stack registration is safe only if a trusted compiler/backend provides authentic scope and lifetime information. Without that instrumentation, U stack pointers remain untracked and are rejected. This is an explicit trust requirement, not a solved generic case.

## Validation and claim boundaries

`tests/runtime_object_layout.cpp` exercises nonpower-of-two element stride and alignment, field interior and exact start, same-type element substitution, cross-element accesses, oversized or overlapping registrations, malformed reallocations, T stack and U global domain checks, copy-based T/U transfer, revocation and address reuse. The cases are **runtime tests**, not claims of deployment-wide instrumentation.

Outstanding integration work includes type descriptor generation at all relevant interfaces, site-authorized registration in every real backend, scope instrumentation where raw U stack pointers are required, and benchmarking of the new layout-aware checks. `void*`, ambiguous unions, flexible array members, unsized/opaque types, and unobserved boundaries must not be counted as covered without explicit interface annotations or additional inference.

The selected source-only provenance study excludes project wrappers and deliberate fault injections. It establishes observed application pointer origins and exercised marshaling paths, **not** an exhaustive denominator of all reachable pointers.

Rejection of malformed U-domain pointers does not by itself prove a trusted
security improvement beyond RLBox confinement and existing bridge checks.
The preregistered H1 comparison evaluates T-visible outcomes and legitimate
content controls; unresolved cases remain inconclusive. The libyaml H2
read-handler test uses a real API with project-authored T-side corruption,
not an upstream libyaml vulnerability or real U-to-T attack.
