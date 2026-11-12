# Stage-two portable recovery smoke

`tools/run_checkpointed_memcached.py` is a small **nonpublication** real-server
runner derived from the earlier equal-work driver. It uses the corrected
independent-v1 client, a fresh server per run, prepopulation, exact warmup and
measurement counts, server counter deltas, and count-only latency checks. It
is not evidence of publication-scale throughput, recovery across VM power
failure, or remote durability until an actual download is verified.

## Frozen plan

Create a JSON specification like this, with actual absolute executable paths:

```json
{
  "server": "/absolute/memcached-rlbox-only",
  "client": "/absolute/memcached-client",
  "server_extra": [],
  "schedule": [{
    "id": "smoke-1", "block": "block-1",
    "clients": 1, "pipeline": 1, "value_bytes": 64, "keys": 16,
    "operations": 10000, "warmup_operations": 1000,
    "expected_get": 10000, "expected_set": 0,
    "warmup_expected_get": 1000, "warmup_expected_set": 0,
    "seed": 2026110901, "get_percent": 100
  }]
}
```

For mixed workloads, independently calculate exact GET/SET counts using the
client's partitioning and RNG schedule; do not infer them from observed results.
Each scheduled identity must be unique. All members of an experimental block
must share its block ID. Initialization copies both executables into `bin/`,
records their SHA-256 digests and the driver digest, and freezes the canonical
plan in the existing checkpoint ledger. Binary paths remain portable. Use the
same driver source when restoring; a changed implementation fails closed.

```sh
python3 tools/run_checkpointed_memcached.py init /tmp/recovery --plan spec.json
python3 tools/run_checkpointed_memcached.py run /tmp/recovery --max-runs 1
python3 tools/run_checkpointed_memcached.py status /tmp/recovery
python3 tools/run_checkpointed_memcached.py export /tmp/recovery /tmp/checkpoint-01.tar.gz
```

Each run has a fresh UUID attempt ID and persists intent **before** launch.
Default execution runs at most one scheduled identity. Completed identities are
never rerun. Any uncertain run or upload blocks further launches. Raw stdout,
stderr, process identities, counter snapshots, and validated results are kept
under the attempt. Completion evidence hashes every output; resume verifies
those hashes, the plan, the driver and executables before doing work. Export
locks out this driver's execution and writes an archive plus a sidecar hash
manifest. Do not modify the ledger concurrently through its generic CLI while
exporting. Export itself does not imply a successful upload.

## Official upload checkpoint, outside measured windows

Use the existing generic ledger CLI and the official Space upload/download
workflow. The benchmark driver does not invoke an unofficial uploader. Export
first, then record the exact archive's upload intent:

```sh
python3 tools/evaluation_checkpoint.py /tmp/recovery start upload-01 \
  --kind upload --details 'Official Space checkpoint; unique checkpoint-01' \
  --artifact /tmp/checkpoint-01.tar.gz
```

Perform the official upload, save its returned file ID/receipt in an evidence
file, download that exact saved file, and only then complete the upload:

```sh
python3 tools/evaluation_checkpoint.py /tmp/recovery complete upload-01 \
  --evidence receipt.json --downloaded /tmp/checkpoint-01-downloaded.tar.gz
```

The ledger rejects a nonmatching download. If upload success is uncertain,
inspect the official destination/receipt and reconcile the existing intent;
do not issue another upload blindly. The archive necessarily predates its own
upload receipt. Keep the verified receipt outside it, and include that receipt
and ledger state in the next checkpoint. A verified downloaded archive may be
restored into a new directory using the externally recorded archive digest:

```sh
python3 tools/run_checkpointed_memcached.py restore \
  /tmp/checkpoint-01-downloaded.tar.gz /tmp/restored --sha256 ACTUAL_SHA256
```

Restore rejects existing destinations, wrong archive hashes, duplicate paths,
links, traversal, unexpected members, mismatched per-file hashes, inconsistent
ledger/plan/binaries/results. Files are written in a fresh staging directory
without tar extraction and become visible at the destination only after
verification. Hashes detect corruption, not malicious replacement of an entire
checkpoint and its independently supplied digest. Archives include executables;
restore only checkpoints from the authorized experiment.

## Interrupted run reconciliation

Failure hooks: `--inject before_launch`, `--inject during_client`, and
`--inject after_result_saved`. They raise errors, preserve the uncertain intent
and available evidence, and clean up process groups. The latter preserves a
valid result without marking it completed, modeling the critical local commit
gap. A result file alone does not authorize treating the run as completed.

On Linux, direct server/client children use parent-death SIGKILL as well as
process-group cleanup on normal exceptions. PID, process group, boot ID and
`/proc/PID/stat` are preserved for manual audit. After an abrupt interruption,
confirm the recorded processes are gone; if a process remains, compare boot ID
and stat field 22 (starttime) before terminating its recorded process group.
Never use indiscriminate `pkill`, and never kill a reused PID. Descendants that
create separate sessions require operator inspection; this smoke uses direct
memcached and client executables. The test hooks are not actual host failure.

After inspecting the evidence and processes, create a written operator record
and explicitly exclude the interrupted attempt through the generic ledger:

```sh
python3 tools/evaluation_checkpoint.py /tmp/restored reconcile ATTEMPT_UUID \
  --outcome excluded --evidence operator-record.txt
python3 tools/run_checkpointed_memcached.py run /tmp/restored --max-runs 1
```

Exclusion (also `not_executed`) excludes the **whole scheduled block**, including
retained successful members from analysis and unlaunched members from execution.
No replacement attempts are scheduled. A completed run in that block remains
on disk for audit only. Do not use generic `completed` reconciliation for an
interrupted run unless its evidence has the driver's exact completion schema
and every result/output is independently validated; exclusion is the intended
recovery policy. A corrupt completed artifact is a hard stop, not grounds for
automatic exclusion or replacement.

Unit fixtures in `tests/checkpointed_memcached.py` test state/restore/corruption
and commit-gap behavior. They are not real-server results. Acceptance should
separately run real executables, inject an interruption, upload and download an
actual checkpoint, restore it elsewhere, exclude the interrupted block, finish
the remaining scheduled identities, then invoke resume again to prove no extra
launch. Check a during-client failure separately for process cleanup.

### Uploading an intentionally uncertain snapshot

The ledger globally blocks new intents while any action is uncertain. Therefore,
when preserving an intentionally interrupted runner, use a **separate transport
ledger**, initialized with a protocol binding the archive SHA-256 and destination.
Record upload intent, official receipt, downloaded bytes and reconciliation in
that transport ledger. Restore the runner snapshot unchanged and demonstrate
that it still blocks before explicit exclusion. Preserve both ledgers and all
transport records in the final evidence. Do not bypass the runner's uncertainty
gate or prematurely reconcile merely to allow an upload.

The helper source hashes are frozen alongside the driver. Completion rechecks
exact counts and zero-error/count-only conditions against the frozen schedule.
Raw files are fsynced before committing completion and attempt directory entries
are synced. These safeguards and process-interruption tests are **not** a proven
machine/power-loss durability guarantee. Timing fields remain raw diagnostic
outputs; no performance comparison or throughput interpretation is supported by
this fixed-count recovery smoke.

The archive also contains the three pinned Python sources under `toolchain/`.
After verification, these support execution from the restored directory with a
compatible Linux/Python runtime and the server/client shared-library dependencies
already installed. This is a fresh-directory recovery check, not a bare-host
bootstrap or a cross-platform executable package. Export holds both the driver
and ledger locks for the entire snapshot.
