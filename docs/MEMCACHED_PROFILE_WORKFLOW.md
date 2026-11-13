# Current-source memcached profile workflow

The corrected collector uses explicit preparation and collection commands. The
old one-command `--out --operations ... --require-coverage` interface is not
supported. Runs [43393783638](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43393783638)
and [43393791474](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43393791474)
failed at that obsolete call, after their matrix verification steps passed.
Later boundary/microbenchmark/report steps did not run in those jobs.

The concurrent compatibility repair `81d4785` first redirected both callers to
`tools/profile_memcached_checks_hosted.py`. That file and all other concurrent
work through `f904ae6` are preserved. This migration changes only the callers to
the stricter current-source wrapper: create-once raw output, count-only client,
retained protocol/failure logs, independent aggregate GET/SET reconciliation,
and final watcher validation. It does not reinterpret the compatibility
collector's historical or future output as frozen v2 evidence.

## Two evidence contracts

- `corrected-profile-v1` retains its original exact client revision, client
  binary, diagnostic binary and server revision pins. Historical evidence is
  not relabeled or upgraded, and its `prepare` interface remains available.
- `source-profile-v2` is a separate current-source contract. `prepare-current`
  builds the client from a clean tracked source revision, records the compiler,
  command, source/binary hashes, and passes ten valid-response count-only
  loopback fixtures (926 responses). It binds that same client to the retained
  fixture logs and binds the diagnostic binary to an existing complete 50-case
  gate and a clean build manifest at the same source revision. These fixture
  runs are functional validation, not application or performance measurements.

Both retain the six fixed scenarios, independent workload seed 20261109,
count-only mode, 5,000 operations and 2,048 keys for ordinary scenarios, and
200,000 operations and 10,000 keys for write-heavy. Preparation freezes all
required inputs before traffic. Collection uses one attempt per scenario,
retains failures and refuses an existing output directory. There are no retries
for missing protected-path coverage. Independent replay still requires exact
raw trace intervals, response counts, no misses or losses, valid watcher
activity and write-heavy LRU activity. A profile is never timing or latency
evidence, and no capacity claim follows from it.

## Invocation

Run only on a user-authorized execution host. Nothing here schedules or
requests another host. Given the matching server build and previously
completed correctness summary:

```sh
bash scripts/run_memcached_profile.sh \
  /absolute/path/new-profile /absolute/path/correctness/summary.json
```

The server build defaults to `${TMPDIR:-/tmp}/interspec-memcached-deployment`;
`INTERSPEC_MEMCACHED_WORK` can select it explicitly. The wrapper consumes and
removes that path-only environment variable for collection. Other unexpected
`INTERSPEC_` variables still cause collection to refuse to run.

The destination's parent must exist. The destination itself must not exist.
The wrapper creates `client-build/`, `frozen/` and `raw/`, then independently
verifies `raw/` against `frozen/plan.json`. Only after replay passes does it
export `check-frequency.json` outside the immutable raw directory. Exported
rates carry workload mode/seed, plan hash, schema, key counts, and explicit
false timing/latency flags. The existing renderer keeps its mode/seed mismatch
gate. The frozen profile and raw records, not the derived rates alone, are the
authoritative evidence.

Both workflow callers use this wrapper. The controlled workflow stores output
under the runner's temporary directory so generated files do not dirty the
source checkout before its build. This is a code migration only: it does not
establish that the controlled host protocol has been fulfilled.

## Focused local checks

```sh
python3 tests/memcached_current_profile.py
python3 tests/memcached_corrected_profile.py
python3 tests/memcached_profile_evidence.py
python3 tests/memcached_workload_metadata.py
bash -n scripts/run_memcached_profile.sh
```

The current-profile test creates a temporary source repository, compiles and
runs the valid-response loopback fixtures, prepares a plan with a clearly
synthetic diagnostic identity, and verifies source/protocol binding failures.
It never launches that diagnostic fixture or an actual memcached server.
A local contract-test pass is not an actual new profile, a successful workflow
run, or a completed full evaluation. No existing historical observation is
changed by these tests.
