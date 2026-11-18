# InterSpec SP3 runtime microbenchmark

VM reference only. Physical core dedication, host stability and contention are unverified. Ranges are observed min/max, not confidence intervals.

Population 2 is the deployment-representative hot-path case: a normal memcached sandbox has two tracked allocations (the bipbuffer object and its persistent input buffer). Larger populations in summary.json show lookup scaling.

| Primitive | Population | Median ns/op | Min–max ns/op | What it isolates |
| --- | ---: | ---: | ---: | --- |
| shared_lock | 2 | 27.56 | 22.24–36.28 | shared metadata-lock acquisition/release |
| metadata_lookup | 2 | 7.25 | 5.34–10.18 | reference, not part of the registry: lookup and containment test in a std::map of the same population, the structure that held the allocation records before the block index |
| type_compare | 2 | 2.45 | 1.42–3.06 | non-inlined type equality with opaque inputs and 1/1024 negative controls |
| bounds_check | 2 | 2.61 | 1.40–3.47 | non-inlined offset/remaining arithmetic with opaque inputs and 1/1024 rejected extents; assumes prior containment |
| check_live | 2 | 8.57 | 5.92–11.00 | production Runtime::check: lock + lookup + type + bounds |
| check_interior | 2 | 8.64 | 5.84–10.50 | production Runtime::check on an interior pointer |
| remaining_bytes | 2 | 8.56 | 6.02–10.19 | production metadata lookup/type check returning remaining extent |
| allocate_from_site | 16384 | 100.16 | 58.55–147.13 | typed allocation registration on queue setup |
| release | 16384 | 226.94 | 155.82–310.06 | trusted allocation metadata release |

Primitive times include loop, non-inlined helper-call and compiler anti-elision controls; they are not baseline-subtracted. Bounds/type checks include one rejected input per 1024 iterations. Allocation and release rows use the explicitly shown 16384-allocation population, not population 2.

Primitive rows are measured independently and therefore are not algebraically additive: the production check executes them in one optimized function and shares instruction/data-cache effects. Use check_live as the direct per-check cost; the smaller rows explain where that cost comes from.
