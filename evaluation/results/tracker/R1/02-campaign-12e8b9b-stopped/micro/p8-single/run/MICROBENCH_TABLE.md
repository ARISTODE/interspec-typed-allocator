# InterSpec SP3 runtime microbenchmark

VM reference only. Physical core dedication, host stability and contention are unverified. Ranges are observed min/max, not confidence intervals.

Population 2 is the deployment-representative hot-path case: a normal memcached sandbox has two tracked allocations (the bipbuffer object and its persistent input buffer). Larger populations in summary.json show lookup scaling.

| Primitive | Population | Median ns/op | Min–max ns/op | What it isolates |
| --- | ---: | ---: | ---: | --- |
| shared_lock | 2 | 24.79 | 21.05–29.86 | shared metadata-lock acquisition/release |
| metadata_lookup | 2 | 5.80 | 5.00–6.45 | ordered allocation lookup and containment test, excluding the lock |
| type_compare | 2 | 1.61 | 0.96–1.96 | non-inlined type equality with opaque inputs and 1/1024 negative controls |
| bounds_check | 2 | 2.22 | 1.20–2.54 | non-inlined offset/remaining arithmetic with opaque inputs and 1/1024 rejected extents; assumes prior containment |
| check_live | 2 | 7.06 | 5.71–8.35 | production Runtime::check: lock + lookup + type + bounds |
| check_interior | 2 | 7.16 | 6.13–8.50 | production Runtime::check on an interior pointer |
| remaining_bytes | 2 | 6.22 | 5.43–7.27 | production metadata lookup/type check returning remaining extent |
| allocate_from_site | 16384 | 96.71 | 53.62–114.41 | typed allocation registration on queue setup |
| release | 16384 | 195.67 | 138.64–236.39 | trusted allocation metadata release |

Primitive times include loop, non-inlined helper-call and compiler anti-elision controls; they are not baseline-subtracted. Bounds/type checks include one rejected input per 1024 iterations. Allocation and release rows use the explicitly shown 16384-allocation population, not population 2.

Primitive rows are measured independently and therefore are not algebraically additive: the production check executes them in one optimized function and shares instruction/data-cache effects. Use check_live as the direct per-check cost; the smaller rows explain where that cost comes from.
