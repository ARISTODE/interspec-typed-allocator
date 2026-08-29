# P7c Multi-Boundary Generalization

P7b made Extended SP3 policy enforcement reusable across a generated boundary. P7c asks the next research question: does the mechanism generalize beyond the rsync/popt proof of concept when the pointer shape and library API change?

## Goal

Demonstrate the same analysis -> generated policy -> `PolicyRuntime` -> RLBox + NaCl enforcement path on multiple real InterSpec evaluation boundaries without adding boundary-specific trusted type/site registration or callback-PC provenance code.

P7c does not require arbitrary ABI marshalling to be generated. Application/library-specific marshalling may remain handwritten, but allocation provenance and pointer type/bounds enforcement must use the common generated policy and `PolicyRuntime` path introduced in P7b.

## Boundary selection

The baseline remains `rsync/popt`. P7c adds three boundaries chosen to exercise qualitatively different pointer patterns already present in the InterSpec evaluation suite.

1. `nginx/libpcre`: an interior pointer returned into a U-owned compiled regular-expression object. The representative use is the name-table pointer returned by PCRE pattern metadata APIs.

2. `yaml/libyaml`: parser/event-owned pointer state with a large structured interface. Internal parser pointers that T never dereferences are not Extended-SP3 uses; P7c focuses only on U-controlled pointers that trusted code actually consumes.

3. `memcached/bipbuffer`: a U-owned data buffer returned together with an extent. This exercises object type/liveness plus spatial validation over a dynamically sized byte range.

These boundaries are intentionally not selected for identical behavior. The acceptance claim requires at least one interior-object pointer, one structured parser/event output, and one buffer-plus-length use.

## Required path for each new boundary

```text
real library source + trusted-use source
              |
              v
      InterSpec / CodeQL analysis
              |
              v
        inferred policy
              |
              v
      boundary policy generator
          /             \
         v               v
U allocation sites    T expected uses
         \               /
          v             v
          PolicyRuntime
               |
               v
          RLBox + NaCl
```

For a source-derived allocation, the allocation instruction itself remains the authority for the trusted `{type_hash, site_id}` metadata. A boundary helper allocation is allowed only when declared in the boundary policy and surrounded by its generated helper-site labels.

## Per-boundary acceptance

A new boundary is considered complete only when all of the following are true.

1. The real upstream source revision is pinned.
2. Allocation policy is derived from source locations or an explicitly declared boundary helper site.
3. Trusted pointer uses carry an expected type and byte extent.
4. The generated policy is registered through `PolicyRuntime`; the bridge does not manually recreate site/type tables.
5. A valid workload succeeds inside RLBox + NaCl.
6. A same-domain pointer backed by a tracked allocation of the wrong expected type/object class is rejected.
7. An untracked U pointer is rejected when it reaches a tracked Extended-SP3 use.
8. Spatial overflow/out-of-object access is rejected for uses with an extent greater than one byte.
9. Existing rsync/popt, P6 evaluation, packaging, and core tests remain green.

## Generalization metrics

`integration/p7c_manifest.json` is the machine-readable source of truth for P7c. `tools/p7c_report.py` reports, per completed boundary:

1. Number of inferred allocation sites.
2. Number and fraction of allocation sites with precise source locations.
3. Number of trusted-use policies.
4. Number of explicitly declared boundary helper sites.
5. Whether the required adversarial classes are exercised.
6. Which pointer-shape category the boundary contributes to the generalization claim.

The report separates generated/source-derived policy from explicit helper policy rather than using handwritten-line counts, which are unstable and mix security mechanism code with unavoidable API marshalling.

`--require-complete` makes the report fail until all three P7c boundaries reach `full` status and satisfy the manifest requirements. CI will enable that mode only once the final boundary is integrated; until then the same report records incremental progress without overstating completion.

## Non-goals and preserved limitations

P7c does not add general control-flow integrity. Reaching an authorized allocation instruction still authorizes that site's type.

P7c does not trust object contents. U remains free to modify bytes inside its allocations; trusted code still validates pointer liveness, expected type, and spatial extent before use.

P7c also does not prove intended-object identity between two simultaneously live allocations that have the same trusted type. The current runtime proves that a pointer is contained in some live allocation of the expected trusted type and that the requested extent remains inside that allocation. Binding a use to one particular same-type allocation would require an additional object-identity relation and remains outside the current claim.

P7c does not introduce physical address reuse. The arena remains bump-only so stale raw pointers cannot become valid again through same-address reallocation.

P7c also does not claim that every InterSpec boundary can be integrated without annotations or API-specific marshalling. The evaluation should report unsupported patterns rather than hiding them behind manual trusted enforcement logic.
