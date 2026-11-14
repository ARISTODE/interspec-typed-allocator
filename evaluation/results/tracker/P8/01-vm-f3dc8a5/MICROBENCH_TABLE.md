# InterSpec SP3 runtime microbenchmark

VM reference only. Physical core dedication, host stability and contention are unverified. Ranges are observed min/max, not confidence intervals.

Population 2 is the deployment-representative hot-path case: a normal memcached sandbox has two tracked allocations (the bipbuffer object and its persistent input buffer). Larger populations in summary.json show lookup scaling.

| Primitive | Population | Median ns/op | Min–max ns/op | What it isolates |
| --- | ---: | ---: | ---: | --- |
| shared_lock | 2 | 22.30 | 22.07–23.45 | shared metadata-lock acquisition/release |
| metadata_lookup | 2 | 5.60 | 5.29–5.88 | ordered allocation lookup and containment test, excluding the lock |
| type_compare | 2 | 1.42 | 1.38–1.98 | non-inlined type equality with opaque inputs and 1/1024 negative controls |
| bounds_check | 2 | 1.40 | 1.37–2.15 | non-inlined offset/remaining arithmetic with opaque inputs and 1/1024 rejected extents; assumes prior containment |
| check_live | 2 | 22.54 | 22.09–27.28 | production Runtime::check: lock + lookup + type + bounds |
| check_interior | 2 | 22.60 | 22.16–26.55 | production Runtime::check on an interior pointer |
| remaining_bytes | 2 | 22.17 | 21.91–28.65 | production metadata lookup/type check returning remaining extent |
| allocate_from_site | 16384 | 78.18 | 72.74–92.64 | typed allocation registration on queue setup |
| release | 16384 | 160.27 | 153.55–172.24 | trusted allocation metadata release |

Primitive times include loop, non-inlined helper-call and compiler anti-elision controls; they are not baseline-subtracted. Bounds/type checks include one rejected input per 1024 iterations. Allocation and release rows use the explicitly shown 16384-allocation population, not population 2.

Primitive rows are measured independently and therefore are not algebraically additive: the production check executes them in one optimized function and shares instruction/data-cache effects. Use check_live as the direct per-check cost; the smaller rows explain where that cost comes from.
