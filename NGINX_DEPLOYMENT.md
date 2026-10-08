# Nginx/PCRE application deployment

This deployment runs the real nginx 1.26.3 server with PCRE 8.45 isolated inside
RLBox wasm2c. The revisions are pinned in `scripts/build_nginx_deployment.sh`.
The existing `integration/nginx_libpcre` driver remains a separate boundary test.

## Implemented boundary

The trusted PCRE ABI bridge implements exactly the functions used by the pinned
nginx core: compile, fullinfo, study, exec, configuration, and cleanup. Native
nginx pointers never enter U. Each compiled expression owns a sandbox. A pool
cleanup registered in nginx destroys its trusted handle and sandbox when the
configuration is discarded, including unsuccessful configuration and reload.

The existing compiled-PCRE allocation helper is used at the actual allocation
in `pcre_compile.c`. The name table is an interior pointer into that object.
Trusted code checks live allocation membership, expected type, and extent
before copying the table. It separately verifies capture counts, entry sizes,
capture indexes, and bounded name termination before nginx consumes the copy.

Regex execution uses persistent subject and integer capture buffers. The
subject is copied into U. U executes the real PCRE interpreter and returns a
capture buffer pointer and extent. The bridge validates this returned range,
copies it into T, and checks every used offset pair against the trusted subject
length before exposing the offsets to nginx. These structural checks are also
present in the RLBox baseline. They do not prove that a match result is true.

The allocation sites are explicit integration helpers. The deployment's
capture/subject staging policy is an explicit extension to the earlier name
table policy, not a claim of automatic discovery from the full nginx program.

## Configurations

| Binary | Isolation | Typed allocations | Final SP3 validation | Fault/trace hooks |
| --- | --- | --- | --- | --- |
| nginx-native | Native PCRE | No | No | No |
| nginx-rlbox-only | RLBox wasm2c | No | No | No |
| nginx-tracked-no-check | RLBox wasm2c | Yes | No | No |
| nginx-interspec | RLBox wasm2c | Yes | Yes | No |
| nginx-diagnostics | RLBox wasm2c | Yes | Yes | Yes |

The ordinary module contains no InterSpec allocation imports. Release modules
contain no fault setter. Tracking-only is a valid-input performance control and
must not be used as an enforcement configuration.

## Validation and measurements

```bash
bash scripts/build_nginx_deployment.sh
python3 tools/test_nginx_deployment.py --out nginx-results/correctness --workers 2
python3 tools/benchmark_nginx.py --out nginx-results/performance \
  --correctness nginx-results/correctness/summary.json \
  --seconds 30 --repetitions 5 --warmup-seconds 3 \
  --threads 4 8 --connections 100
```

The application test drives all five variants through named and unnamed
captures, optional unmatched groups, case-insensitive matching, rewrites, maps,
non-matches, query strings, HEAD, keepalive, and concurrent clients. Invalid
configuration must fail. Optional worker tests exercise fork and two reloads on
native and InterSpec servers. In a restricted root container, omit `--workers`
and record worker/reload coverage as untested locally; hosted CI runs it as an
unprivileged user.

Faults are injected in U on the actual name-table and capture-offset return
paths. Wrong type, untracked, released, and excessive extent must abort before
trusted copying. A valid same-type replacement is accepted. A separate control
uses an in-bounds typed allocation with an invalid capture offset to exercise
the application's value validation.

Each measurement uses real regex routing after 16 preceding regex locations.
The workload matches the selected 100-connection, 30-second, 4/8-client-thread
shape. The default server is one nginx event loop (`master_process off`);
`--workers N` selects a master and N workers and is recorded in the environment.
Do not confuse the wrk thread count with nginx's worker count.

The harness checks every HTTP status and response body. It rejects response
errors, missing validations, connection/read/write errors, timeouts, server
failure, and binary hashes different from the passing correctness run. Every
repetition contains all four variants in a reproducibly shuffled order. It saves
raw wrk output, per-run samples, p50/p99 latency, server CPU cost, aggregate RSS,
startup time, source/binary hashes, environment, and paired throughput ratios.
Aggregate RSS includes pages shared between workers.

Publication measurements require controlled hardware, enough repetitions,
fixed power policy, and a verified load-generator capacity margin. The Lua
response checker has a client cost and must remain identical across variants.
Use disjoint `--server-cpus` and `--client-cpus` sets when appropriate. Hosted
and shared-container results are reference evidence; a small or negative
incremental difference does not establish a speedup.

## Scope and limits

This is the PCRE8 interpreter boundary, not PCRE2, OpenSSL/TLS, or JIT. All four
variants use the same pinned PCRE build without JIT. The bridge covers the nginx
event loop and does not support arbitrary third-party threaded PCRE callers or
the complete public PCRE API. Subject size is capped at 65,536 bytes; the capture
buffer contains 4,096 integers; the typed arena is 1 MiB per compiled expression.
Capacity failures fail closed. Each expression's arena and U heap are reclaimed
when its sandbox is destroyed, rather than by physical typed-address reuse.

SP3 does not establish intended-object identity among live allocations of the
same type, integrity of regex results, or arbitrary concurrent-mutation safety.
The application validators establish bounds and structure, not truth of U data.
