# Selected application evaluation status

Verified on 2026-10-09. The selected Extended-SP3 boundaries are rsync/popt,
memcached/bipbuffer, YAML/libyaml, and nginx/PCRE8.

[EVALUATION_READINESS.md](EVALUATION_READINESS.md) now audits the application
results and microbenchmarks together. All four application references are
present, but all planned results are **not** ready. The audit revalidated 334
application samples, 195 repeated runtime samples across 39 configurations,
and the four P8 boundary summaries. The audited published head `9d99966` passed
the core, memcached, P10 and nginx PR workflows.

The nginx implementation is published in [draft PR #20](https://github.com/ARISTODE/interspec-typed-allocator/pull/20),
stacked on PR #19. The measured implementation commit is `e9ab463`.

## Implementation and validation

| Boundary | Application integration | Verified evidence | Remaining evaluation |
| --- | --- | --- | --- |
| rsync/popt | Real transfers with popt isolated in RLBox wasm2c | 12 rejected pointer attacks; four configurations; 15 paired repetitions for each of three workloads | Controlled hardware rerun |
| memcached/bipbuffer | Worker logs, watchers, and asynchronous LRU queues isolated | 50/50 deployment cases; six-scenario reference matrix; primitive costs and diagnostic counts | Tracking-only matrix cells; longer controlled runs; direct write-heavy check-frequency profile; Native-to-RLBox cost and boundary-frequency breakdown |
| YAML/libyaml | Full parser workload in RLBox wasm2c | Matching outputs; four rejected pointer controls; 15 paired repetitions of 1 MiB × 1,000 parses | Controlled hardware rerun |
| nginx/PCRE8 | Real nginx server with isolated PCRE | Clean CI build of five variants; 24/24 cases including workers/reloads; 40 valid timed runs; CPU/RSS/p99 collected | Controlled hardware rerun |

The nginx worker/reload validation gap is closed. Native and InterSpec both
pass two-worker operation and two graceful reloads. The tests require distinct
worker generations, changed regex routes, concurrent requests after reload,
and clean worker exits.

## Reference numbers

[SELECTED_EVALUATION_RESULTS.md](SELECTED_EVALUATION_RESULTS.md) is the consolidated
12-row table. [The CSV](evaluation/results/selected/summary.csv) and
[JSON](evaluation/results/selected/summary.json) are generated from paired raw
samples; the source SHA-256 manifest is checked in alongside them.

| Main reference | Native | RLBox | InterSpec | Paired InterSpec delta vs RLBox |
| --- | ---: | ---: | ---: | ---: |
| rsync, 194 MiB transfer (ms) | 613.280 | 613.998 | 616.161 | +0.37% runtime |
| YAML, 1 MiB × 1,000 parses (ms) | 4287.155 | 5813.376 | 5810.707 | +0.01% runtime |
| nginx, four wrk threads (Kreq/s) | 62.724 | 54.895 | 54.881 | -0.58% throughput loss |
| nginx, eight wrk threads (Kreq/s) | 60.305 | 53.672 | 54.518 | -0.77% throughput loss |

Memcached's six rows are in the consolidated table. They use one-second smoke
measurements with three paired repetitions, not its planned 30-second,
15-repetition publication protocol. The timed write-heavy measurements record
nonzero LRU moves with no drops; the separate 1,000-operation diagnostic profile
still observes zero direct SP3 checks and cannot support a check-cost correlation.

Paired percentages need not equal ratios of the displayed medians. Negative
values and small differences are not established speedups. The earlier local
nginx reference and older five-repetition YAML reference remain separate datasets.

## CI evidence on the published implementation

The [2026-10-09 CI audit](evaluation/results/selected/ci-audit-20261009.json)
records passing PR workflows at `9d99966`. The runs below identify the
implementation validation associated with the selected nginx timing artifact.

* [Nginx 37835791042](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37835791042): build, all 24 application cases, full timing matrix, and artifact upload succeeded.
* [Core CI 37835790921](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37835790921): all jobs passed, including 20/20 core tests and the application corruption experiments.
* [Memcached 37835790903](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37835790903): 50/50 deployment cases and the measurement pipeline passed.
* [P10 37835790953](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37835790953): memcached, nginx, and YAML library boundaries passed.

The selected timing datasets are pinned independently: YAML workflow 37593628736,
memcached workflow 37593628863, nginx workflow 37835791042, and the checked-in
rsync paired CSV. Original hosted artifacts and their checksums are preserved.

All selected applications now have implementations and reference numbers.
Publication evaluation is still incomplete: controlled hardware and the
specified memcached follow-ups remain necessary. The draft stack #15 through
#20 also remains unmerged. This selection does not cover all ten manuscript
boundaries or constitute a fresh evaluation of all original SP1/SP2/SP3 policies.
