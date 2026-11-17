# InterSpec SP3 runtime microbenchmark

VM reference only. Physical core dedication, host stability and contention are unverified. Ranges are observed min/max, not confidence intervals.

Population 2 is the deployment-representative hot-path case: a normal memcached sandbox has two tracked allocations (the bipbuffer object and its persistent input buffer). Larger populations in summary.json show lookup scaling.

| Primitive | Population | Median ns/op | Min–max ns/op | What it isolates |
| --- | ---: | ---: | ---: | --- |
| shared_lock | 2 | 24.22 | 20.53–26.35 | shared metadata-lock acquisition/release |
| metadata_lookup | 2 | 6.28 | 5.14–7.36 | ordered allocation lookup and containment test, excluding the lock |
| type_compare | 2 | 1.78 | 1.34–2.42 | non-inlined type equality with opaque inputs and 1/1024 negative controls |
| bounds_check | 2 | 2.22 | 1.63–2.91 | non-inlined offset/remaining arithmetic with opaque inputs and 1/1024 rejected extents; assumes prior containment |
| check_live | 2 | 24.17 | 20.44–28.93 | production Runtime::check: lock + lookup + type + bounds |
| check_interior | 2 | 24.30 | 20.55–27.35 | production Runtime::check on an interior pointer |
| remaining_bytes | 2 | 22.26 | 20.39–27.16 | production metadata lookup/type check returning remaining extent |
| allocate_from_site | 16384 | 78.06 | 67.42–127.83 | typed allocation registration on queue setup |
| release | 16384 | 181.35 | 146.85–236.05 | trusted allocation metadata release |

Primitive times include loop, non-inlined helper-call and compiler anti-elision controls; they are not baseline-subtracted. Bounds/type checks include one rejected input per 1024 iterations. Allocation and release rows use the explicitly shown 16384-allocation population, not population 2.

Primitive rows are measured independently and therefore are not algebraically additive: the production check executes them in one optimized function and shares instruction/data-cache effects. Use check_live as the direct per-check cost; the smaller rows explain where that cost comes from.
