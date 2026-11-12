# Durable original matrix collection

This mode invokes the existing matrix and collector, all four variants and all
six original scenario shapes, including live watchers. It does not establish a
controlled host or authorize a long experiment. Rehearsal reports explicitly
state `publication_ready=false` and `evidence_scope=vm_recovery_rehearsal`.

Initialize only after source freeze (replace paths as appropriate):

```
python tools/benchmark_memcached_matrix.py checkpoint init /tmp/matrix-state \
  --work /path/to/memcached-build --correctness-summary /path/to/summary.json \
  --client-binary /path/to/memcached_client --allow-one-interruption-replacement -- \
  --functional-rehearsal --preset smoke --repetitions 3 \
  --seconds 0.1 --warmup 0.1 --operations 20000 --warmup-operations 2000
python /tmp/matrix-state/tools/benchmark_memcached_matrix.py checkpoint run /tmp/matrix-state --max-scenarios 1
python /tmp/matrix-state/tools/benchmark_memcached_matrix.py checkpoint run /tmp/matrix-state --inject during_collection
```

Fixed work overrides the client's wall-time termination. It uses exact equal
operation totals, with deterministic independent operation choices indexed by
ticket. Timed and warmup work remain separate. Incidental rates are provenance,
not publication results. Three repetitions yield 72 measured rows in a complete
grid. A scenario block contains every variant and repetition; no partial pairing
can enter a report.

The injection is an exception followed by verified child-group cleanup, not a
SIGKILL or power-loss simulation. Real driver death uses Linux parent-death
signals throughout the process tree. Launch uses a separate frozen exec guard,
not Python preexec_fn while watcher threads are active. Before exporting an
uncertain state or reconciling, independently confirm no original collector,
server, or client remains active; process IDs are audit data, never blind kill
instructions.

```
python /tmp/matrix-state/tools/benchmark_memcached_matrix.py checkpoint status /tmp/matrix-state
python /tmp/matrix-state/tools/benchmark_memcached_matrix.py checkpoint export /tmp/matrix-state /tmp/matrix-state.tgz --confirm-no-active-processes
```

Transfer the archive through the official external Space mechanism and download
it again; compare the returned archive SHA-256. The collector does not upload.
Restore to a fresh path using the frozen toolchain that created the archive:

```
python /tmp/matrix-state/tools/benchmark_memcached_matrix.py checkpoint restore /tmp/download.tgz /tmp/matrix-restored --sha256 EXPECTED
python /tmp/matrix-restored/tools/benchmark_memcached_matrix.py checkpoint reconcile /tmp/matrix-restored ATTEMPT_ID \
  --reason 'Verified interruption and no remaining original processes' \
  --retry-whole-scenario --confirm-no-active-processes
python /tmp/matrix-restored/tools/benchmark_memcached_matrix.py checkpoint run /tmp/matrix-restored
```

Without `--retry-whole-scenario`, reconciliation permanently excludes the entire
scenario. Such a grid emits `grid_complete=false` and exits nonzero. Replacement
is possible only if predeclared at initialization, only once per scenario, and
only for an uncertain interrupted attempt. Observed collector failures cannot
be replaced. Completed quality failures are retained and not rerun. Replacement
never depends on the sign of an overhead or measured loss. Original attempt
files and hashes are retained even after replacement.

Every invocation verifies frozen plan, sources, tools, correctness binding,
client and server binaries, and completed/excluded evidence. Resume skips only
verified completed scenarios. Completion inventory includes stdout/stderr,
commands, raw samples, stats and logs. Unique attempt and report directories
prevent overwriting old evidence. The per-invocation lock spans child execution;
archive generation holds that lock and the ledger lock. Safe restore rejects
path traversal, links, duplicates, digest mismatches and existing destinations.
Original absolute paths inside archived provenance remain historical records;
new execution uses the restored root's bundled binaries and tools.

Final reports are under `STATE/reports/UUID/`, with canonical per-scenario
subdirectories suitable for `tools/verify_memcached_matrix.py`.
