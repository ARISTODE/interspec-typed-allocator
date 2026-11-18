# InterSpec SP3 runtime microbenchmark

VM reference only. Physical core dedication, host stability and contention are unverified. Ranges are observed min/max, not confidence intervals.

Population 2 is the deployment-representative hot-path case: a normal memcached sandbox has two tracked allocations (the bipbuffer object and its persistent input buffer). Larger populations in summary.json show lookup scaling.

| Primitive | Population | Median ns/op | Min–max ns/op | What it isolates |
| --- | ---: | ---: | ---: | --- |
| shared_lock | 2 | 22.29 | 21.67–24.89 | shared metadata-lock acquisition/release |
| metadata_lookup | 2 | 5.81 | 5.57–7.22 | reference, not part of the registry: lookup and containment test in a std::map of the same population, the structure that held the allocation records before the block index |
| type_compare | 2 | 1.43 | 1.37–2.36 | non-inlined type equality with opaque inputs and 1/1024 negative controls |
| bounds_check | 2 | 1.76 | 1.72–2.75 | non-inlined offset/remaining arithmetic with opaque inputs and 1/1024 rejected extents; assumes prior containment |
| check_live | 2 | 22.64 | 21.69–27.41 | production Runtime::check: lock + lookup + type + bounds |
| check_interior | 2 | 22.38 | 22.05–25.83 | production Runtime::check on an interior pointer |
| remaining_bytes | 2 | 22.26 | 21.98–28.82 | production metadata lookup/type check returning remaining extent |
| allocate_from_site | 16384 | 73.73 | 71.84–123.45 | typed allocation registration on queue setup |
| release | 16384 | 171.23 | 159.33–270.95 | trusted allocation metadata release |

Primitive times include loop, non-inlined helper-call and compiler anti-elision controls; they are not baseline-subtracted. Bounds/type checks include one rejected input per 1024 iterations. Allocation and release rows use the explicitly shown 16384-allocation population, not population 2.

Primitive rows are measured independently and therefore are not algebraically additive: the production check executes them in one optimized function and shares instruction/data-cache effects. Use check_live as the direct per-check cost; the smaller rows explain where that cost comes from.
