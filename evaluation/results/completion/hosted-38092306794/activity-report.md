# Memcached SP3 check frequency

Ordinary profiles drive 5000 fixed client operations; write_heavy drives 200000. Counts include client traffic and the declared asynchronous drain; preload and watcher setup are excluded. These diagnostic builds do not provide timing results.

| Scenario | Client ops | SP3 checks | Checks/op | Checks/1k ops | offer_input | peek_all | poll | push | request |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| balanced_1c | 5000 | 54 | 0.0108 | 10.8 | 0 | 1 | 1 | 26 | 26 |
| balanced_8c | 5000 | 60 | 0.0120 | 12.0 | 0 | 4 | 4 | 26 | 26 |
| read_heavy_1k | 5000 | 748 | 0.1496 | 149.6 | 0 | 4 | 4 | 370 | 370 |
| write_heavy | 200000 | 2070 | 0.0103 | 10.3 | 0 | 35 | 35 | 1000 | 1000 |
| watch_light | 5000 | 36164 | 7.2328 | 7232.8 | 7500 | 3326 | 2300 | 7769 | 15269 |
| watch_moderate | 5000 | 31063 | 6.2126 | 6212.6 | 7500 | 266 | 259 | 7769 | 15269 |

## Boundary activity

| Scenario | Sandbox calls/op | Bytes into U/op | Bytes from U/op | LRU holds/takes | Moves to warm | Coverage valid |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| balanced_1c | 0.0414 | 0.0832 | 0.1664 | 26/26 | 30 | True |
| balanced_8c | 0.0404 | 0.0832 | 0.1664 | 26/26 | 30 | True |
| read_heavy_1k | 0.2468 | 1.1840 | 2.3680 | 370/370 | 461 | True |
| write_heavy | 0.1566 | 0.0800 | 0.1600 | 1000/1000 | 1000 | True |
| watch_light | 14.3126 | 245.3376 | 639.4750 | 269/269 | 269 | True |
| watch_moderate | 9.5800 | 245.3176 | 639.4150 | 269/269 | 269 | True |

The operation columns name the actual protected bridge paths (for example request, push, offer_input, peek, peek_all, or poll). These counts are workload frequencies, not timing measurements.
