# Nginx/PCRE application results

The actual pinned nginx server runs PCRE 8.45 inside RLBox wasm2c. These shared-environment timings are reference measurements, not controlled-hardware publication results.

## Correctness and enforcement

The application suite passes **22/22 cases**. All five variants pass normal HTTP routing, named/optional/case-insensitive captures, rewrites, maps, non-matches, HEAD, keepalive, and concurrent requests. Invalid regex configuration fails in every variant.

* Eight source-injected invalid pointers reject on actual name-table and capture-offset paths: wrong type, untracked, released, and excessive extent on each path.
* A structurally invalid capture offset in a valid typed allocation rejects before nginx uses it.
* Two valid same-type substitutions remain accepted with preserved contents, as expected from the current identity limitation.
* The routing profile executes 1,800 successful metadata checks over 100 requests: **18 checks/request**, with no typed allocations during the measured requests.
* The existing core regression suite passes 20/20.

The name-table check runs during configuration. The steady-state count consists of 17 subject-buffer checks and one capture-buffer check per selected routing request. These buffers are part of the application adapter; the measurement therefore covers the current deployment policy, including its explicit staging extensions.

**Multiple-worker and graceful-reload coverage is pending.** The local suite uses one nginx event loop; the checked-in CI workflow adds worker/reload tests.

On 2026-10-08 the complete build script was run from a fresh dependency checkout
at `1b8cbc6`. All five variants built successfully, and the application suite
again passed **22/22 cases**. The core suite also passed **20/20**. This closes
the local clean-script build gap recorded in the original provenance file.
New build hashes, test output, and build logs are preserved separately under
`evaluation/results/nginx-pcre/validation-20261008/`; the original performance
samples still refer to their original binaries and have not been replaced.

The strengthened reload gate requires new worker PIDs, a changed regex route,
concurrent requests after each reload, and clean worker exits. Native nginx's
worker startup reports `initgroups(root, 0) failed (1: Operation not permitted)`
in this container, so that gate still requires the unprivileged CI host.

## Four-way reference

Configuration: 100 connections, 30 seconds per measurement, 3 seconds warmup per run, 5 paired repetitions, wrk thread counts [4, 8], nginx workers option 0 (0 means one event loop with master_process off). All HTTP status codes and response bodies were validated.

| wrk threads | Native Kreq/s | RLBox Kreq/s | Tracking Kreq/s | InterSpec Kreq/s | InterSpec vs RLBox | InterSpec vs Native | Paired InterSpec/RLBox loss range |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 4 | 124.800 | 98.868 | 95.890 | 91.255 | +5.17% | +27.54% | +2.29% to +12.89% |
| 8 | 120.861 | 96.726 | 93.971 | 93.000 | +3.55% | +21.92% | -4.12% to +6.13% |

Percentages are medians of paired throughput-loss ratios, 100 × (1 − target / baseline). They need not equal ratios of the displayed medians. Negative values and small differences are not treated as established speedups.

| wrk threads | Variant | Median p99 µs | Median startup ms | Median CPU µs/request | Median aggregate RSS KiB |
| ---: | --- | ---: | ---: | ---: | ---: |
| 4 | native | 2608.000 | 22.737 | unavailable | unavailable |
| 4 | rlbox-only | 2360.000 | 22.667 | unavailable | unavailable |
| 4 | tracked-no-check | 3151.000 | 22.989 | unavailable | unavailable |
| 4 | interspec | 3090.000 | 22.814 | unavailable | unavailable |
| 8 | native | 2886.000 | 22.350 | unavailable | unavailable |
| 8 | rlbox-only | 2262.000 | 23.037 | unavailable | unavailable |
| 8 | tracked-no-check | 2355.000 | 23.039 | unavailable | unavailable |
| 8 | interspec | 2314.000 | 22.058 | unavailable | unavailable |

Per-process CPU/RSS may be unavailable in a restricted PID namespace. Missing values are preserved, not replaced by zero. The load generator and server share the host; client capacity and scheduler interference still require controlled-host evaluation.

## Evidence and scope

Raw samples, generated summaries, correctness cases, per-case traces, HTTP configurations, wrk outputs, binary hashes, and environment metadata are retained under `evaluation/results/nginx-pcre/`. Every timed binary matches the correctness gate. The implementation and reproduction steps are in [NGINX_DEPLOYMENT.md](NGINX_DEPLOYMENT.md).

This deployment is PCRE8 without JIT. It does not complete PCRE2/OpenSSL/TLS evaluation, general threaded PCRE API support, or same-type object identity enforcement. The nginx worker/reload CI gate and controlled-hardware publication runs remain separate from local functional completion.
