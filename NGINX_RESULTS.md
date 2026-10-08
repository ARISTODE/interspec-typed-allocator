# Nginx/PCRE application results

The actual pinned nginx server runs PCRE 8.45 inside RLBox wasm2c. These shared-environment timings are reference measurements, not controlled-hardware publication results.

## Correctness and enforcement

The application suite passes **24/24 cases**. All five variants pass normal HTTP routing, named/optional/case-insensitive captures, rewrites, maps, non-matches, HEAD, keepalive, and concurrent requests. Invalid regex configuration fails in every variant.

* Eight source-injected invalid pointers reject on actual name-table and capture-offset paths: wrong type, untracked, released, and excessive extent on each path.
* A structurally invalid capture offset in a valid typed allocation rejects before nginx uses it.
* Two valid same-type substitutions remain accepted with preserved contents, as expected from the current identity limitation.
* The routing profile executes 1,800 successful metadata checks over 100 requests: **18 checks/request**, with no typed allocations during the measured requests.
* The existing core regression suite passes 20/20.

The name-table check runs during configuration. The steady-state count consists of 17 subject-buffer checks and one capture-buffer check per selected routing request. These buffers are part of the application adapter; the measurement therefore covers the current deployment policy, including its explicit staging extensions.

Multiple-worker and graceful-reload application tests passed.

## Four-way reference

Configuration: 100 connections, 30 seconds per measurement, 3 seconds warmup per run, 5 paired repetitions, wrk thread counts [4, 8], nginx workers option 0 (0 means one event loop with master_process off). All HTTP status codes and response bodies were validated.

| wrk threads | Native Kreq/s | RLBox Kreq/s | Tracking Kreq/s | InterSpec Kreq/s | InterSpec vs RLBox | InterSpec vs Native | Paired InterSpec/RLBox loss range |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 4 | 62.724 | 54.895 | 55.161 | 54.881 | -0.58% | +12.56% | -2.71% to +5.74% |
| 8 | 60.305 | 53.672 | 54.611 | 54.518 | -0.77% | +10.02% | -2.24% to +1.56% |

Percentages are medians of paired throughput-loss ratios, 100 × (1 − target / baseline). They need not equal ratios of the displayed medians. Negative values and small differences are not treated as established speedups.

| wrk threads | Variant | Median p99 µs | Median startup ms | Median CPU µs/request | Median aggregate RSS KiB |
| ---: | --- | ---: | ---: | ---: | ---: |
| 4 | native | 1755.000 | 22.669 | 15.943 | 3884.000 |
| 4 | rlbox-only | 1994.000 | 22.744 | 18.223 | 9936.000 |
| 4 | tracked-no-check | 2004.000 | 22.817 | 18.135 | 52812.000 |
| 4 | interspec | 2066.000 | 23.106 | 18.215 | 52840.000 |
| 8 | native | 1729.000 | 22.784 | 16.584 | 3884.000 |
| 8 | rlbox-only | 1968.000 | 22.713 | 18.626 | 9936.000 |
| 8 | tracked-no-check | 1957.000 | 22.724 | 18.312 | 52844.000 |
| 8 | interspec | 1985.000 | 22.693 | 18.343 | 52828.000 |

Per-process CPU/RSS may be unavailable in a restricted PID namespace. Missing values are preserved, not replaced by zero. The load generator and server share the host; client capacity and scheduler interference still require controlled-host evaluation.

## Evidence and scope

Raw samples, generated summaries, correctness cases, per-case traces, HTTP configurations, wrk outputs, binary hashes, and environment metadata are retained under `evaluation/results/nginx-pcre/`. Every timed binary matches the correctness gate. The implementation and reproduction steps are in [NGINX_DEPLOYMENT.md](NGINX_DEPLOYMENT.md).

This deployment is PCRE8 without JIT. It does not complete PCRE2/OpenSSL/TLS evaluation, general threaded PCRE API support, or same-type object identity enforcement. The worker/reload CI gate passed; controlled-hardware publication runs remain outstanding.

## Selected CI run and earlier reference

The selected dataset is [workflow 37835791042](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37835791042), artifact 11577172659, from implementation head `e9ab463`. Its source-file hashes match the final reporting worktree. The artifact checksum, checked-out merge commit, build manifest, and raw samples are retained under `evaluation/results/nginx-pcre/hosted-37835791042/`.

The earlier local reference remains in the parent directory and reported +5.17% / +3.55% paired throughput loss for four/eight wrk threads. Those samples are not pooled with this CI run. The different reference results reinforce the need for controlled measurements before making a precise overhead claim.
