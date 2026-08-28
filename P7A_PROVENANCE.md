# P7a Allocation-Site Provenance

P7a strengthens the trusted allocation contract for precise source-derived policies. Earlier phases made T authoritative over the meaning of each `TypeId`, but compromised U could still choose any registered `TypeId` when requesting a tracked allocation. P7a removes that choice from the generated allocation path.

## Security invariant

For an allocation site selected by InterSpec analysis, the authoritative object type is determined by the trusted policy for the instruction that performs the allocation. U does not supply the type or allocation-site identifier as ordinary callback data.

The resulting path is:

```text
CodeQL allocation site
        ↓
source span + inferred type
        ↓
generated site labels around allocation instruction
        ↓
direct NaCl callback syscall at that instruction
        ↓
trusted NaCl callback program counter
        ↓
T site-range lookup
        ↓
trusted {base, size, type_hash, site_id}
```

If U invokes the same allocator callback syscall from an instruction that is not registered as an authorized allocation site, T cannot find a matching site and the allocation is rejected.

## Why a site identifier argument is insufficient

A site identifier, TypeId, nonce, or claimed return address supplied as ordinary U data cannot establish allocation provenance: compromised U can copy or replay such values. P7a therefore derives provenance from execution state captured by the trusted NaCl service runtime.

The generated allocation expression invokes the existing NaCl callback syscall directly instead of calling a reusable U allocation helper. The patched, pinned NaCl service runtime records the sandbox program-counter state at callback syscall entry before the host callback runs. The RLBox backend exposes that trusted callback state to T.

## Generated policy

For each precise CodeQL allocation fact, `tools/generate_policy.py` assigns a `SiteId` and emits global begin/end symbols around the selected allocation expression. The generated T policy records the site id, expected type id, and symbol names. At sandbox initialization, T resolves those symbols and registers non-overlapping trusted instruction ranges with `interspec::Runtime`.

The precise generated U path no longer passes a `TypeId` to allocation. Legacy hand-written policies without source locations retain the older TypeId-based instrumentation only for backward compatibility; they do not receive the P7a site-provenance guarantee.

## Runtime metadata

Tracked allocation metadata now includes:

```text
{base, size, type_hash, site_id}
```

`Runtime::allocate_from_pc()` accepts an allocation only when the trusted callback program counter falls inside a registered site range. The selected site's trusted type binding determines the stored `type_hash`. `reallocate()` preserves the original allocation's `type_hash` and `site_id`; it cannot relabel provenance.

## Adversarial tests

The synthetic RLBox + NaCl test exercises two provenance attacks.

First, U invokes the allocator callback syscall from an unregistered instruction. The callback slot is known to U, but the trusted program counter does not match any allocation policy, so allocation fails.

Second, U creates an object through the legitimate `Other` allocation site and overwrites its bytes to look exactly like `Item`. The stored provenance and type remain those of the `Other` site, so a T use expecting `Item` is rejected as `wrong_type`.

The real rsync/popt path also uses site provenance. CodeQL-derived `poptGetContext` and `expandNextArg` allocation sites are registered from generated labels. The typed string-copy site used by the boundary bridge is registered explicitly as a trusted `char` allocation site. The complete P4c rsync regression continues to require successful execution with popt inside RLBox + NaCl.

## Scope and limitation

P7a proves allocation-site provenance, not arbitrary control-flow provenance. If compromised U legitimately reaches an authorized allocation instruction, an allocation from that instruction receives that site's type. Preventing unintended control-flow from reaching the instruction would require a stronger control-flow or capability mechanism and is outside P7a.

P7a also does not change object contents: U remains free to corrupt bytes inside its writable memory. T trusts only the allocation metadata it owns. Existing liveness, type, and spatial-bound checks remain required before T consumes a U-controlled pointer.
