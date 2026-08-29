# P7b Native InterSpec Integration

P7a established allocation-site provenance. P7b removes typed-allocation mechanism code from application-specific bridges so the normal integration path becomes analysis -> generated policy -> reusable enforcement runtime -> sandbox backend.

## Goal

A new InterSpec boundary should not need to reimplement trusted type registration, allocation-site symbol resolution, callback-PC provenance lookup, or the dispatch from an allocation callback into `Runtime::allocate_from_pc()`.

Application-specific code may still be required to marshal a library's API. For example, rsync's popt bridge must still translate option tables, argv arrays, and destination slots. P7b does not claim to generate arbitrary API marshalling. The goal is narrower: application glue should express application semantics, while Extended SP3 enforcement uses reusable InterSpec components.

## Integrated path

```text
CodeQL / InterSpec analysis
        |
        v
generated allocation + use policy
        |
        +---- U allocation-site instrumentation
        |
        +---- T type/site/access policy
                    |
                    v
          interspec::PolicyRuntime
                    |
                    v
             RLBox + NaCl
```

`PolicyRuntime` owns the trusted `Runtime` instance and centralizes generated type/site registration and allocation callback provenance dispatch. It is backend-interface based rather than including RLBox headers directly: a compatible backend exposes symbol lookup and callback program-counter access.

## Reusable policy runtime

`include/interspec/policy_runtime.h` provides the common binding. `initialize_from_sandbox()` combines generated trusted type registration with generated allocation-site registration using the backend's symbol resolver. `allocate_from_callback()` obtains trusted callback execution state from the backend and performs the provenance-aware allocation lookup. An unregistered callback instruction still fails closed.

`tests/policy_runtime.cpp` validates the contract independently of RLBox with an authorized site, an unauthorized site, and a compatible backend that exposes the authoritative post-syscall PC separately.

## Boundary policy generation

`tools/generate_boundary_policy.py` composes the existing source-derived policy generator with boundary-specific policy data. Precise CodeQL allocation sites continue to be instrumented from their exact source spans. A boundary may additionally declare helper allocation sites, such as a trusted copy helper needed to marshal an API, without maintaining a second T-side registration table.

The generator emits:

1. U allocation-site instrumentation for precise analyzed sites.
2. U begin/end macros for declared boundary-helper sites.
3. T type, source-site, helper-site, and trusted-use policy in one namespace.
4. A single `register_allocation_policy()` entry point covering every generated allocation site.

Helper sites are policy declarations, not a claim that arbitrary application marshalling is automatically inferred. Code that invokes such a helper still has to place the generated begin/end macros around the authorized allocation instruction.

## rsync/popt migration

`integration/rsync_popt/boundary.json` declares the typed string-copy allocation as a `char` helper site. The manually maintained `site_provenance.h` registration table has been removed. The generated U policy supplies the helper-site labels, and the generated T policy registers both the CodeQL-derived `poptGetContext` / `expandNextArg` sites and the string-copy helper through the same `register_allocation_policy()` call.

`integration/rsync_popt/p4c_bridge.cpp` now owns `PolicyRuntime` rather than duplicating type registration, symbol resolution, allocation-site registration, and callback-PC fallback logic. Its remaining responsibilities are application-specific popt/rsync marshalling: copying argv and option metadata, constructing U shadow slots, synchronizing results, and validating strings before copying them back to T.

The synthetic RLBox provenance test is migrated to the same `PolicyRuntime` path so the reusable interface is exercised independently of the rsync bridge.

## Acceptance criteria

P7b is accepted only when all of the following hold:

1. The reusable policy runtime unit test passes.
2. Boundary-policy code generation tests pass, including unknown helper-type rejection.
3. The synthetic provenance attacks still reject unauthorized allocation sites and wrong-site shape confusion.
4. The real isolated rsync/popt malicious pointer tests still pass.
5. The complete rsync P4c workload still runs with popt inside RLBox + NaCl.
6. Core correctness, policy inference, P6 evaluation, and release smoke remain green.

## Scope

P7b generalizes the Extended SP3 mechanism integration, not arbitrary interface generation. A new library with a different ABI can still require application-specific code to marshal complex tables, callbacks, or output slots. What P7b removes is the need for that bridge to implement its own trusted type/site registration or callback provenance machinery.

The P7a security limitations remain unchanged. Allocation-site provenance does not imply control-flow integrity, U-controlled object contents remain untrusted, and the current arena still avoids physical address reuse.
