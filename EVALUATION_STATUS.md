# Selected application evaluation status

Audit date: 2026-10-08 UTC. Selected boundaries are rsync/popt,
memcached/bipbuffer, YAML/libyaml, and nginx/PCRE. This selection does not include
all ten boundaries in the attached InterSpec manuscript.

## Existing application evidence at 255c877

| Boundary | Application isolation and implementation | Existing evidence | Remaining publication work |
| --- | --- | --- | --- |
| rsync/popt | Real transfers with popt in RLBox wasm2c | Application correctness; 12 rejected pointer attacks; four configurations; 15 paired hosted repetitions for 194 MiB sync | Controlled hardware rerun; review/merge |
| memcached/bipbuffer | Worker logs, watchers, and asynchronous LRU queues isolated | 50/50 deployment cases; six-workload hosted matrix; primitive costs and check frequencies | Native-to-RLBox boundary-cost decomposition; controlled longer runs; nonzero protected-LRU coverage for the write-heavy frequency profile; review/merge |
| YAML/libyaml | Full parser workload in RLBox wasm2c | Matching outputs; four pointer rejection controls; four configurations; 1 MiB × 1,000 parses | Controlled hardware rerun; review/merge |
| nginx/PCRE8 | Real nginx server with PCRE in RLBox wasm2c, locally validated | Fresh clean build of five variants; 22/22 application cases; 40 timed runs, four configurations, 4/8 wrk threads, five paired repetitions | Worker/reload and remote CI; controlled hardware; publication of local branch |

The existing implementation work remains in the open draft stack #15 → #16 →
#17 → #18 → #19. It is not all merged into main. The latest YAML branch's CI,
memcached deployment, P10 boundary tests, and YAML workflow all succeeded.
The nginx continuation is on `evaluation/nginx-pcre-full`. Its local clean build
and 22 application cases passed again at `1b8cbc6`; remote CI and worker/reload
validation are pending. The reload gate now requires new worker
PIDs, successful responses through a changed regex route after each reload,
concurrent requests on both new configurations, and successful worker exits.
Native nginx workers report `initgroups(root, 0)` permission failures locally.
Automatic approval review rejected the GitHub push because explicit permission
to publish the repository contents was required. No nginx PR was opened.

## Timing evidence must be identified by run

Rsync's checked-in reference reports 613.280 / 613.998 / 614.371 / 616.161 ms
for Native / RLBox / tracking / InterSpec on the 194 MiB workload. Its paired
incremental InterSpec overhead is +0.37% versus RLBox.

The checked-in YAML report is a five-repetition run at 5061877 and reports
+2.48%. A newer passing run at the PR merge revision cdef5b8 completed **15**
paired repetitions, each with **1,000 parses**, and reports:

| Native ms | RLBox ms | Tracking ms | InterSpec ms | Paired InterSpec versus RLBox |
| ---: | ---: | ---: | ---: | ---: |
| 4287.155 | 5813.376 | 5766.793 | 5810.707 | +0.01% |

Source: [YAML workflow 37593628736](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37593628736),
job 112700820709, artifact 11471505440. This audit checked the workflow log;
the older checked-in sample files remain their original run's evidence. Do not
mix their samples or present the newer timing as a controlled-machine result.

Memcached's latest checked branch also passed
[workflow 37593628863](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37593628863),
including the six-scenario matrix, check-frequency profile, and microbenchmark
steps. `MEMCACHED_EVALUATION_REPORT.md` and `MEMCACHED_PERFORMANCE_PLAN.md`
explicitly retain the write-heavy coverage gap. A zero in that short profile
does not establish that the workload never exercises SP3.

GitHub status was rechecked on 2026-10-08: draft PRs #15 through #19 remain open
and mergeable; the latest YAML-head CI, memcached, P10, and YAML jobs succeeded.
The nginx evidence archive's SHA-256 matches its recorded checksum, and its
40 raw timing rows match the two five-repetition, four-variant summaries.

Application deployment, hosted reference measurements, and controlled
publication evaluation are separate milestones. The first three selected
applications have implementation and reference numbers; it is not accurate to
say that every final evaluation number is complete.

## New nginx reference

The local full reference uses 100 connections, 30-second windows, and five paired
repetitions for 4 and 8 wrk threads. Median paired InterSpec throughput loss
versus RLBox is +5.17% and +3.55%, respectively. Every response in all 40 timed
runs passed validation. Nginx runs as one event loop in this reference.

The configuration-time name-table check and the adapter's steady-state subject
and capture-buffer checks are both implemented. The latter execute 18 checks
per selected request. `NGINX_RESULTS.md` reports the full four-way comparison,
paired ranges, p99 latency, and missing CPU/RSS counters. This local result does
not complete the pending worker/reload CI or controlled-hardware gate.
