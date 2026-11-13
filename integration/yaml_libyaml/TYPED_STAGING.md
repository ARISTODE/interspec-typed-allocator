# Ordinary YAML typed staging

`typed_staging_identity` is an opt-in mode of `yaml_app_bench.cpp`. It runs the
same real libyaml parser as the existing modes, with a project-authored staging
bridge. The native, `rlbox_only`, `tracked_no_check` and `extended_sp3` modes
retain their existing allocation/check contracts. This is not a new SP1/SP2 or
all-policy selector.

## Trusted contract

A typed element is one `interspec_yaml_scalar_staging` aggregate, containing an
8192-byte unsigned-char payload. The shared C/C++ header asserts payload offset
zero, aggregate size 8192 and alignment one. An individual char is not the typed
element: that would only permit a one-byte checked access.

After Engine construction, trusted setup registers this layout for the existing
generated scalar type and allocates exactly one element in the reserved Wasm
arena. It retains the nonzero Runtime allocation result as a `uintptr_t`, checks
its width and full extent, and then passes the checked uint32 offset to the new
`interspec_yaml_setup_with_staging(uint32_t, uint32_t)` export. These are global
Wasm linear-memory offsets, not arena-relative offsets or host addresses. The
expected base is never learned or refreshed from a guest scalar return.

Before each copy, trusted code checks sandbox membership, the complete returned
range, the supported length below 8192, and the four-argument
`Runtime::check_typed_element` with the independently retained expected base.
Only an `ok` result reaches the existing post-check observation and copy. Zero
is rejected explicitly because the generic API uses a zero expected base to
permit free object selection. Empty scalars still check their object; embedded
NUL bytes are copied by explicit length, not by string functions. The guest
reserves one terminator byte and checks the original length before narrowing.

The extent constraint largely coincides with legacy staging bounds. The added
contract is an exact typed-element start and the trusted selected staging base.
This is spatial identity of that staging aggregate, not the identity of an
original libyaml allocation or proof that bytes belong to the current event.
The same aggregate intentionally persists across events and parse iterations.
No per-event generation, temporal/ABA protection, source-derived coverage or
invalid-pointer rejection effectiveness is claimed.

## Ownership and compatibility

The original `interspec_yaml_setup(uint32_t)` export remains helper-owned.
The new export rejects a zero supplied offset and never owns the supplied
allocation. Guest reset/shutdown releases only helper-owned staging. Trusted
new-mode setup permits one attempt per Engine and retains an allocation even
when later setup checks fail. A guest-setup-attempt flag is recorded before the
invocation, independently of successful setup.

Before printing success, new-mode `finish()` performs one guest shutdown and
one checked metadata release. Legacy `finish()` is a no-op. Shutdown attempt is
recorded before invocation, so an exception never causes a guest retry. The
no-throw destructor handles unfinished paths; if shutdown threw, it destroys
the sandbox before releasing remaining metadata and makes no more guest calls.
Normal-path release failure is an error, not a successful cleanup observation.
The full input-copy extent is checked in all modes, preserving valid-input
behavior while checking more than starting-address confinement.

The generated allocation policy remains unchanged: zero precise source-derived
sites, two helper declarations and one dynamic-byte scalar use. New-mode staging
is explicitly allocated by trusted application code, not by source inference.
No generic runtime, generator, backend or other application contract is changed.

## Evaluation scope

The Stage20 evaluation plan separately freezes seven valid documents, iterations
one and two, and five modes (70 processes). Six documents use prior independent
scalar/event oracles; one contains a valid 8191-byte scalar. Counts, decoded-byte
totals, ordered-byte rolling hashes and existing observation sequences are
specified before application execution. Five separate one-iteration controls use
a valid 8192-byte scalar: native is expected to parse, while the four sandbox
modes are expected to exit with the supported staging-capacity limit. The full
plan has 75 outcomes: 71 successful parses and four expected limit exits, not
75 successful parses or security rejections. Both checked modes and tracked-no-check
share the same typed executable. Compiled-path review must confirm the actual
metadata/type/extent and expected-base comparisons; counters alone are not proof.

This document specifies the implementation contract, not a passing test result.
No timing or security-effectiveness claim follows from valid-input parsing.
The aggregate output/hash oracle does not establish complete YAML semantics or
collision-proof equality. Build identities, finite commands and independent
review/results belong to the separately retained Stage20 evidence.
