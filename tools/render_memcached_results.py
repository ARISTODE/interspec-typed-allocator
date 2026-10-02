#!/usr/bin/env python3
"""Render the recorded complete-server evidence without hand-entered timings."""
import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--results', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
correctness = json.loads((a.results/'correctness-summary.json').read_text())
perf = json.loads((a.results/'performance-summary.json').read_text())
env = json.loads((a.results/'environment.json').read_text())
tracking = json.loads((a.results/'tracking-summary.json').read_text())
commit = env['build']['project_commit']
lines = [
    '# Memcached deployment results', '',
    f"The complete cache-server deployment passes **{correctness['passed']}/{correctness['total']}** local cases. Performance results below are a **shared-container pilot**, not publication overhead estimates.", '',
    f'Implementation and measured binaries: `{commit}`.', '',
    'The fresh-build [memcached deployment CI run](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/36977024146) passed its build, 50-case correctness gate, and performance-collection step at this implementation revision.', '',
    'The [implementation guide](MEMCACHED_DEPLOYMENT.md) documents the boundary, source edits, threat scope, build, tests, and collection commands. [PR #16](https://github.com/ARISTODE/interspec-typed-allocator/pull/16) is stacked on the SP3 diagnostics work in #15.', '',
    '## What now runs', '',
    '* The actual pinned memcached 1.6.45 cache server runs with bipbuffer in RLBox wasm2c.',
    '* All three uses are covered: worker logs, watcher output, and asynchronous LRU item bumps.',
    '* T checks U pointer type, extent, and live allocation metadata before accessing bytes. It then works on stable T snapshots.',
    '* The logger validates record structure and parser indexes. LRU queues carry one-use handles; T retains native item pointers and verifies their lock hashes before use.',
    '* Native, RLBox-only, tracking-only, full SP3, and diagnostic builds execute the normal-operation suite. Release builds exclude trace/fault code.', '',
    'The LRU handle protection is a material addition discovered during deployment: an outer buffer check alone would leave the native pointers inside LRU records exposed to corruption. Those pointers now stay in T.', '',
    '## Correctness and enforcement', '',
    '| Evidence | Result |', '| --- | --- |',
    '| Normal-operation groups | 5 variants × 16 checks pass |',
    '| Pointer corruption | 36/36 reject: 3 queue roles × 3 paths × 4 errors |',
    '| Same-type substitutions | 3/3 accepted, as expected from SP3 scope |',
    '| Application validation controls | 4/4 reject: invalid log event, forged LRU handle, wrong item hash, split LRU record |',
    '| Upstream watcher tests | 47/47 assertions for native; 47/47 for SP3 |',
    '| Core runtime regression suite | 20/20 CTest tests pass |', '',
    'These suites overlap; their counts are not independent security guarantees. The 50 top-level cases comprise 5 normal groups, 36 pointer attacks, 7 scope/application controls, and 2 upstream suites.', '',
    'Normal checks include asynchronous LRU bumps, set/get flags, add/replace, CAS, append/prepend, counters, a 256 KiB binary value, multiget, touch/delete, fragmented requests, invalid commands, expiry, flush, watcher contents, 2,000 operations from four concurrent clients, and 25 watcher reconnects. The upstream test assertions are unchanged; their copied launcher selects loopback TCP.', '',
    'Representative actual rejection messages:', '', '```text',
    'INTERSPEC_REJECT boundary=memcached_bipbuffer operation=peek_all reason=wrong_type',
    'INTERSPEC_REJECT boundary=memcached_bipbuffer operation=peek_all reason=untracked',
    'INTERSPEC_REJECT boundary=memcached_bipbuffer operation=peek_all reason=out_of_bounds',
    'INTERSPEC_REJECT boundary=memcached_logger reason=malformed_record',
    'INTERSPEC_REJECT boundary=memcached_bipbuffer operation=lru_take reason=unknown_handle',
    'INTERSPEC_REJECT boundary=memcached_bipbuffer operation=lru_take reason=wrong_item_hash',
    'INTERSPEC_REJECT boundary=memcached_bipbuffer operation=lru_extent reason=malformed_record',
    '```', '',
    'An ordinary untracked pointer and a released tracked pointer both produce `untracked`; the latter has a preceding successful metadata release. Invalid pointers terminate with SIGABRT. Same-type substitution controls preserve valid contents and demonstrate the limit of the allocation check.', '',
    '## Allocator trace evidence', '',
    f"The diagnostic normal run created {tracking['events']['allocate_from_site']} tracked allocations across {sum(tracking['roles'].values())} sandbox instances: {tracking['roles']['worker']} worker loggers, {tracking['roles']['lru']} LRU queues, and {tracking['roles']['watcher']} watcher instances including churn.", '',
    f"It recorded {tracking['events']['check']} allocation checks, {tracking['events']['release']} releases, and {tracking['events']['lru_hold']} / {tracking['events']['lru_take']} trusted LRU handle creations / consumptions. Event counts reflect this workload and scheduling, not a universal operation cost.", '',
    '| Allocation site | Size (bytes) | Count |', '| --- | ---: | ---: |',
]
for row in tracking['allocations']:
    lines.append(f"| {row['site_id']} | {row['bytes']} | {row['count']} |")
lines += ['', 'Site 1048577 is the real `bipbuf_t` allocation, including its 20-byte Wasm header. Site 1048578 is the persistent character input buffer. T staging, handle maps, backend memory, and native item allocations are additional memory and are reflected in process RSS.', '',
    '## Performance pilot', '',
    f"Configuration: {env['parameters']['clients']} loopback clients, pipeline depth {env['parameters']['pipeline']}, four server workers, {env['parameters']['keys']} keys, {env['parameters']['value_bytes']}-byte values, {env['parameters']['get_percent']}% GETs, {env['parameters']['warmup']}-second warmup, {env['parameters']['seconds']}-second measurement, {env['parameters']['repetitions']} paired repetitions per variant/workload. Variant order is shuffled reproducibly. The worker/watcher buffers are 1 MiB / 4 MiB for every variant.", '',
    f"CPU quota: `{env['cpu_quota']}`. Memory limit: `{env['memory_limit']}` bytes. CPU governor: `{env['governor']}`. Server/client affinity was not pinned for this pilot. Both run in the same shared environment.", '',
    '| Workload | Variant | Median ops/s | Min–max ops/s | Median run p99 (µs) | Median CPU µs/op | Median RSS (MiB) | No log/LRU losses in all runs |',
    '| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |']
for r in perf:
    lines.append(f"| {r['workload']} | {r['variant']} | {r['ops_per_s_median']:,.0f} | {r['ops_per_s_min']:,.0f}–{r['ops_per_s_max']:,.0f} | {r['p99_us_median']:.2f} | {r['cpu_us_per_op_median']:.2f} | {r['VmRSS_kib_median']/1024:.2f} | {'yes' if r['all_no_log_loss'] and r['all_no_lru_loss'] else 'NO'} |")
lines += ['', '| Workload | SP3 throughput loss vs native | vs RLBox-only | vs tracking-only |', '| --- | ---: | ---: | ---: |']
for r in perf:
    if r['variant'] != 'interspec': continue
    lines.append(f"| {r['workload']} | {r['throughput_loss_vs_native_paired_median_pct']:.2f}% | {r['throughput_loss_vs_rlbox-only_paired_median_pct']:.2f}% | {r['throughput_loss_vs_tracked-no-check_paired_median_pct']:.2f}% |")
lines += ['',
    'Percentages are medians of paired per-repetition ratios, `100 × (1 − SP3 throughput / baseline throughput)`. Negative values do not establish a speedup. These short, unpinned measurements can vary with scheduling and background load. The components have different denominators and are not additive.', '',
    'The client validates every response. Response latency includes pipelining and is a closed-loop measurement. CPU counters include final deferred logger work; RSS is sampled after the run. `cache_only` can exercise LRU queues; `watch_active` additionally exercises logging. Logs and LRU drops must be considered when comparing throughput. Earlier high-load development pilots showed log drops and are not used as paper overhead evidence.', '',
    'The four timed release binary hashes match the correctness gate. Upstream tests use separate debug builds; their exact tested hashes are retained in the correctness summary. Recompiling coverage-enabled debug objects can change their build hashes without changing the source.', '',
    '## Remaining paper evaluation', '',
    '* Run repeated longer measurements on controlled hardware, with disjoint CPU affinity and a client-capacity check; retain raw run-level samples and uncertainty.',
    '* Sweep concurrency, pipeline depth, value size, working-set size, and read/write mix, including active watchers and LRU activity. Report log/LRU loss alongside throughput and latency.',
    '* Measure longer-term watcher churn, memory growth, startup, and sustained queue pressure. Evaluate saturation with a separate load generator where appropriate.',
    '* Extend deployment to any additional configurations claimed in the paper, including extstore/proxy/TLS/SASL if in scope; nginx and YAML applications remain separate work.',
    '* Review and merge the implementation PRs after their CI gates. A passing test suite is experimental evidence for these cases, not a formal proof or exhaustive compatibility claim.', '',
    '## Reproducibility artifacts', '',
    '* [Correctness cases and tested binary hashes](evaluation/results/memcached-deployment/correctness-summary.json)',
    '* [Raw performance samples](evaluation/results/memcached-deployment/samples.csv)',
    '* [Performance summary](evaluation/results/memcached-deployment/performance-summary.json)',
    '* [Build provenance](evaluation/results/memcached-deployment/build-manifest.json)',
    '* [Host and workload parameters](evaluation/results/memcached-deployment/environment.json)',
    '* [Tracking summary](evaluation/results/memcached-deployment/tracking-summary.json)',
    '* [Complete raw evidence archive](evaluation/results/memcached-deployment/evidence.tar.gz), including per-case stderr/stdout, watcher records, upstream outputs, per-run stats, build logs, generated policy, and SHA-256 manifest.', '',
    'Regenerate this report with `python3 tools/render_memcached_results.py --results evaluation/results/memcached-deployment --output MEMCACHED_RESULTS.md`.', '']
a.output.write_text('\n'.join(lines))
