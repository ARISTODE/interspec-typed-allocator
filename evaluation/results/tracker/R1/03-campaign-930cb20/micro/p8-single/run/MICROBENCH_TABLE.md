# InterSpec SP3 runtime microbenchmark

VM reference only. Physical core dedication, host stability and contention are unverified. Ranges are observed min/max, not confidence intervals.

Population 2 is the deployment-representative hot-path case: a normal memcached sandbox has two tracked allocations (the bipbuffer object and its persistent input buffer). Larger populations in summary.json show lookup scaling.

| Primitive | Population | Median ns/op | Min–max ns/op | What it isolates |
| --- | ---: | ---: | ---: | --- |
| shared_lock | 2 | 24.87 | 18.88–27.87 | shared metadata-lock acquisition/release |
| metadata_lookup | 2 | 5.34 | 4.68–6.94 | ordered allocation lookup and containment test, excluding the lock |
| type_compare | 2 | 1.47 | 0.93–2.25 | non-inlined type equality with opaque inputs and 1/1024 negative controls |
| bounds_check | 2 | 1.48 | 1.08–2.54 | non-inlined offset/remaining arithmetic with opaque inputs and 1/1024 rejected extents; assumes prior containment |
| check_live | 2 | 5.88 | 4.91–7.75 | production Runtime::check: lock + lookup + type + bounds |
| check_interior | 2 | 6.66 | 5.47–7.77 | production Runtime::check on an interior pointer |
| remaining_bytes | 2 | 5.62 | 4.86–7.01 | production metadata lookup/type check returning remaining extent |
| allocate_from_site | 16384 | 55.42 | 50.94–98.98 | typed allocation registration on queue setup |
| release | 16384 | 155.49 | 136.63–224.34 | trusted allocation metadata release |

Primitive times include loop, non-inlined helper-call and compiler anti-elision controls; they are not baseline-subtracted. Bounds/type checks include one rejected input per 1024 iterations. Allocation and release rows use the explicitly shown 16384-allocation population, not population 2.

Primitive rows are measured independently and therefore are not algebraically additive: the production check executes them in one optimized function and shares instruction/data-cache effects. Use check_live as the direct per-check cost; the smaller rows explain where that cost comes from.
