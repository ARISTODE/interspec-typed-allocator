# InterSpec SP3 runtime microbenchmark

Population 2 is the deployment-representative hot-path case: a normal memcached sandbox has two tracked allocations (the bipbuffer object and its persistent input buffer). Larger populations in summary.json show lookup scaling.

| Primitive | Median ns/op | Min–max ns/op | What it isolates |
| --- | ---: | ---: | --- |
| shared_lock | 8.45 | 7.83–8.90 | shared metadata-lock acquisition/release |
| metadata_lookup | 4.45 | 4.32–4.48 | ordered allocation lookup and containment test, excluding the lock |
| type_compare | 1.54 | 1.54–1.65 | expected-type hash equality check |
| bounds_check | 1.64 | 1.54–1.75 | offset/remaining-byte arithmetic and extent comparison |
| check_live | 11.66 | 11.55–11.80 | production Runtime::check: lock + lookup + type + bounds |
| check_interior | 11.94 | 11.89–12.01 | production Runtime::check on an interior pointer |
| remaining_bytes | 11.87 | 11.85–11.90 | production metadata lookup/type check returning remaining extent |
| allocate_from_site | 76.50 | 74.64–80.45 | typed allocation registration on queue setup |
| release | 38.91 | 37.95–40.19 | trusted allocation metadata release |

Primitive rows are measured independently and therefore are not algebraically additive: the production check executes them in one optimized function and shares instruction/data-cache effects. Use check_live as the direct per-check cost; the smaller rows explain where that cost comes from.
