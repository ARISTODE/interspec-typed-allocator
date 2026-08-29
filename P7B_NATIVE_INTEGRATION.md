# P7b Native InterSpec Integration

P7a established allocation-site provenance. P7b removes typed-allocation mechanism code from application-specific bridges so the normal integration path becomes analysis -> generated policy -> reusable enforcement runtime -> sandbox backend.

## Goal

A new InterSpec boundary should not need to reimplement trusted type registration, allocation-site symbol resolution, callback-PC provenance lookup, or the dispatch from an allocation callback into `Runtime::allocate_from_pc()`.

Application-specific code may still be required to marshal a library's API. For example, rsync's popt bridge must still translate option tables, argv arrays, and destination slots. P7b does not claim to generate arbitrary API marshalling. The goal is narrower: application glue should express application semantics, while Extended SP3 enforcement uses reusable InterSpec components.

## Target path

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

## Acceptance criteria

1. The reusable policy runtime is independently unit tested with an authorized site, an unauthorized callback site, and a backend that exposes the authoritative return PC separately.
2. Generated policy integration no longer relies on application-specific copies of type/site registration logic.
3. The rsync/popt bridge uses the reusable policy runtime for Extended SP3 allocation enforcement; remaining bridge code is popt/rsync marshalling rather than allocator-policy plumbing.
4. Boundary-helper allocation sites such as the typed string copy are represented by policy data instead of a separate hand-maintained trusted registration table.
5. Core tests, policy inference, P6 evaluation, release smoke, the synthetic provenance attacks, the real popt boundary, and the complete rsync P4c path all remain green.

## Current first milestone

`include/interspec/policy_runtime.h` introduces the common binding. It supports generated type/site initialization using a backend symbol resolver and performs fail-closed allocation dispatch from trusted callback PC state. `tests/policy_runtime.cpp` validates the reusable contract without depending on RLBox.

The remaining P7b work is to migrate the generated policy and rsync/popt integration onto this common path and eliminate the remaining manually registered helper site.
