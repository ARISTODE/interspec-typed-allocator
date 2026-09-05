# P10 RLBox wasm2c Multi-Boundary Generalization

P10 extends the P9b RLBox wasm2c implementation from the rsync/popt baseline to all three P7c generalization boundaries. The security mechanism is unchanged: T owns authoritative allocation metadata and validates U-controlled pointers for liveness, expected type, and complete spatial extent before trusted use.

## Goal

Demonstrate that the same source analysis, generated policy, trusted allocation-site provenance, and `PolicyRuntime` checks used by P9b work across qualitatively different pointer shapes on the wasm2c backend used by the InterSpec paper.

P10 covers:

1. `memcached/bipbuffer`: a precise source-derived `bipbuf_new()` allocation and an interior `bipbuf_peek_all()` pointer with a runtime byte extent.
2. `nginx/libpcre`: a PCRE name-table pointer that refers inside a compiled regular-expression object allocated through the `pcre_malloc` abstraction.
3. `yaml/libyaml`: a nested scalar-value pointer and runtime length returned from a U-owned structured event.

## Provenance and policy path

P10 reuses P9b's wasm-direct allocation-site provenance. Each authorized precise allocation site or explicit boundary helper site receives a unique direct Wasm import. U supplies only the requested allocation size. The trusted host wrapper embeds the corresponding SiteId, and T maps that SiteId to the authoritative TypeId before recording `{base, size, type_hash, site_id}`.

Precise source-derived sites and explicit helper sites remain distinct. The memcached/bipbuffer object allocation is source-derived. PCRE and libyaml use explicit generated helper sites because their selected allocations occur through allocator abstractions rather than direct `malloc` syntax.

## Security acceptance

For each P7c boundary, the wasm2c integration exercises the valid trusted-use path and rejects the P7c adversarial classes applicable to that pointer shape:

1. tracked same-domain memory with the wrong trusted type is rejected with `wrong_type`;
2. ordinary same-domain sandbox memory without trusted metadata is rejected with `untracked`;
3. a valid pointer paired with a corrupted runtime extent is rejected with `out_of_bounds`.

P9b already exercises logical lifetime invalidation and stale-pointer rejection on the same wasm2c runtime path. P10 focuses on reproducing P7c's multi-boundary type and spatial checks on wasm2c.

## Reproduction

```bash
chmod +x scripts/run_p7c_wasm2c.sh
./scripts/run_p7c_wasm2c.sh
```

The driver clones the pinned RLBox wasm2c backend and the pinned upstream source revision for each boundary, regenerates wasm-direct policy artifacts, builds one combined Wasm module, and runs `integration/p7c_wasm_smoke.cpp`.

A successful run ends with:

```text
InterSpec P10: memcached/bipbuffer passed in RLBox wasm2c
InterSpec P10: nginx/libpcre passed in RLBox wasm2c
InterSpec P10: yaml/libyaml passed in RLBox wasm2c
InterSpec P10: all P7c generalization boundaries passed on wasm2c
```

## Completion evidence

P10 is complete on commit `196ed706cb4f32a27a4330d4054219ada17a8aaf` of the implementation branch. GitHub Actions run `33720131714` completed successfully and produced the four success markers above. The repository's existing `ci` workflow also completed successfully for the same commit, preserving core tests, CodeQL policy regeneration, the NaCl P7c regression, P8 evaluation, P9a, and the original P9b rsync/popt wasm2c path.

## Preserved limitations

P10 does not add general control-flow integrity, parser-output content integrity, intended-object identity among multiple live allocations of the same type, or temporal identity under physical address reuse. Application-specific ABI marshalling remains outside the generic Extended-SP3 mechanism. These are the same limitations retained by P7c and P9b.