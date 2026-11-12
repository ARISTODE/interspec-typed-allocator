# Corrected-client stage 1 protocol and recovery contract

Status: protocol proposal and locally tested recovery primitive, **not a passed
capacity gate or a completed performance evaluation**. No paper edits. The
currently authorized VM is a reference environment, not a verified dedicated or
controlled host. Do not label VM repetitions as independent host sessions.

## Why the previous numbers cannot close this gate

The 2026-11-09 count-only/sampled-capacity report records 100 exact-work runs in
one VM execution epoch. Four/five-CPU windows were about 3–4 seconds. Identical
A/A comparisons varied substantially, and fifth-CPU intervals were too broad for
tight equivalence. Sampled mode also showed an approximately 8.7% throughput
reduction in one scenario. Neither nonsignificance nor aggregate spare client
CPU proves generator headroom. Prior legacy/full-instrumentation observations
must remain separate from corrected independent-v1 count-only results.

## Freeze before confirmatory measurement

The following numbers are **proposed**, not represented as user-agreed thresholds
or measured properties. Obtain explicit agreement on the scientific tolerance
and freeze a machine-readable plan before the confirmatory run. Changes require
a new protocol ID and new confirmatory data; never tune the margin after results.

- Proposed equivalence margin: throughput ratio [0.98, 1.02] for both identical
  A/A and baseline-versus-added-client-resource comparisons, in each scenario.
  A different smallest scientifically meaningful effect must be agreed and
  frozen if 2% is inappropriate.
- Proposed first gate scenarios: balanced_8c and read_heavy_1k, preserving their
  original key count, concurrency, pipeline, value size and target GET fraction.
  Passing these is not evidence for every workload. Recheck headroom for each
  scenario/topology in the later matrix before interpreting its throughput.
- Proposed configurations: count4-A, count4-B (identical binary and arguments,
  labels only), count5 (one additional equivalent physical client core), and
  count1 (positive CPU saturation control). Do not silently substitute an SMT
  sibling or a shared virtual CPU for an additional equivalent physical core.
- Proposed replication: 12 independently initialized measurement sessions across
  at least three days, four complete balanced blocks per session. Sessions reset
  the server, corpus, processes and warmup, and record a distinct host epoch.
  Temporal separation alone does not establish statistical independence; inspect
  persistent host effects and disclose residual correlation. If independence
  remains unsupported, do not issue an independence-based equivalence claim.
- Use a randomized four-treatment Williams design within each session: rows
  A B D C; B C A D; C D B A; D A C B. Freeze the RNG implementation, random seed,
  label permutation, row order and scenario order in the plan. This balances
  position and directed adjacency. Generate the full schedule before executing.
- Separate unscored pilot data determine exact operations per scenario and an
  exact warmup count. Choose work sufficient for **at least 60 seconds even for
  the fastest configuration**, and warmup targeting at least 15 seconds. Freeze
  these counts for all compared configurations and all confirmatory sessions.
  No duration-terminated comparison and no adaptation to interim outcomes.
  An unexpectedly shorter measured window fails this duration gate; retain it,
  revise the protocol and rerun all affected comparisons rather than pooling.
- Use the same independent-v1 workload seed within each block, different seeds
  across blocks. Precompute exact expected operation/GET/SET counts independently
  of the measured client. Verify all completed responses, values, error counts,
  drops and relevant server/logger counters. Record both requested and realized
  mix. A measurement failure invalidates the paired block, not just the slow run.

The frozen plan must include protocol ID, agreed margin, session/block schedule,
all commands and arguments, source commit plus uncommitted patch SHA256, compiler
and build flags, server/client binary SHA256, workload generator and measurement
mode, key/type/sample domain definitions, seeds, warmup and operation counts,
CPU placements, environment manifest, analysis formulas, exclusions, and stopping
rule. The prior report's client SHA256 is provenance only; hash the binary
actually used and establish its relation to the source before every session.

## Controlled-host and measurement gate

Before confirmatory execution document host owner/exclusivity evidence, physical
core/SMT/NUMA topology, server/client placement with no overlap, CPU governor and
frequency/turbo policy, thermal conditions, OS/kernel, network topology and
interrupt placement, background processes, and virtualization/steal-time status.
Record what is verifiable and what is unavailable. Do not infer exclusivity from
successful CPU affinity or low average CPU use. Avoid concurrent builds, uploads,
compression, watchers and analysis during timed runs. Collect process CPU over
the exact timed workload, not whole-process startup/sorting, plus per-thread or
per-core evidence where available. Missing hardware counters remain a limitation. Server stats surround subprocess
startup and asynchronous drain, while the client interval runs from work release
(go) through joins. Do not describe server CPU equivalents as measured over the
identical client interval or as cycle-accurate per-request attribution.

If the controlled-host requirement cannot be established on the authorized VM,
only functional/recovery tests and explicitly labeled exploratory runs proceed.
A host requirement is a scientific gate, not permission to provision or spend on
a different host. Ask before acquiring new resources.

Count-only is the primary throughput mode. Quantiles must be null/unavailable in
those rows. Sampled latency is a separate experiment with frozen rate/cap and
zero sample drops; overflow invalidates quantiles. Report achieved load, sample
counts, quantile uncertainty and batch-send-to-response-validation semantics.
Never attach sampled quantiles to count-only runs or describe a sample maximum
as the maximum over all requests. A future sampled/full comparison needs its own
interference gate and analysis, not an assumption of free instrumentation.

## Predeclared inference and stopping

For each complete block calculate log(Q_B/Q_A) and log(Q_5/Q_A). The baseline is A,
not a post hoc choice of A, B or their mean. Average log ratios within a session;
these session means, not requests or blocks, are the replication units. For each
scenario and contrast, form the conventional two-sided 90% Student-t interval
with n-1 degrees of freedom across the 12 session means, then exponentiate the
limits. This is the two one-sided tests equivalence procedure at alpha 0.05.
Document the independence and distributional assumptions; residual correlation
or gross violations block this planned claim rather than justify a convenient
replacement analysis after looking at results.

A gate passes only when **every** predeclared A/A and added-resource interval lies
strictly inside [0.98, 1.02], quality/host/duration gates pass, and the positive
control shows detectable resource sensitivity. Proposed positive-control
criterion: the corresponding 90% interval for count1/A lies wholly below 0.90.
This is an intersection-union all-must-pass decision, not a selection of favorable
contrasts. Report all estimates and intervals, including failures. Secondary
analyses are labeled exploratory and cannot rescue a failed primary gate.

Stop at the frozen schedule, not when an interval first passes. No variance-based
extension, optional stopping, selective outlier removal or performance-based
reruns. Interrupted/corrupt/uncertain blocks remain recorded and excluded from
primary analysis. With fewer than the 12 complete planned sessions, the planned
confirmatory gate is incomplete; any replacement design is frozen separately,
with all attempts reported. Generate a fresh report from the current frozen manifest and actual observations.
Existing historical renderer narrative and static CI claims are not evidence for
this release; do not copy them into a new result without revalidation.
Successful stage 1 permits designing the later matrix,
not retrospectively validating old bars or claiming a code optimization.

## Checkpoint and resume contract

`tools/evaluation_checkpoint.py` is a **local POSIX ledger**, not a benchmark
scheduler, statistical analyzer, upload client, remote durability service or
automatic resumer. It uses only Python's standard library. Run its standalone
checks with `python3 tests/evaluation_checkpoint.py`. No existing collectors are
automatically connected to it. Integration and end-to-end remote recovery remain
future gates before a multi-hour matrix.

Create the ledger directory on a persistent local filesystem and ensure its
parent directory creation is durable. Network filesystems and storage that ignore
fsync are not covered. Under an advisory process lock, snapshots are written to
a same-directory temporary file, fsynced, atomically replaced, then the directory
is fsynced. SHA256-checked content-addressed blobs hold the frozen plan, results
and upload evidence. The envelope checks the canonical state hash. Every status
read verifies referenced blobs. These detect accidental corruption, not malicious
rewriting or rollback of the entire ledger. Use an independently stored manifest
hash for provenance. Unreferenced blobs/temp files after a crash are not results.
Do not delete them while a writer is running.

Example local workflow (paths and IDs are illustrative):

```
mkdir -p /persistent/eval-ledger
python3 tools/evaluation_checkpoint.py /persistent/eval-ledger init --plan plan.json
python3 tools/evaluation_checkpoint.py /persistent/eval-ledger start s01-b01-A --kind run --details 'protocol=P1 session=01 block=01 config=A seed=42'
# Only after start exits successfully: execute the exact frozen run externally.
# Validate counts/errors and collect its full output and environment evidence.
python3 tools/evaluation_checkpoint.py /persistent/eval-ledger complete s01-b01-A --evidence validated-run.json
python3 tools/evaluation_checkpoint.py /persistent/eval-ledger status
```

Every start persists an `uncertain` intent **before** any external action, with a
unique never-reused attempt ID. The ordinary `complete` call is for the original
uninterrupted caller after it verified success. The utility does not itself
validate experiment output; evidence must contain the actual result and quality
checks, not merely an assertion. Any crash or lost acknowledgment requires the
operator's explicit `reconcile`, even if the action probably did not start.
Do not use `complete` to bypass post-crash reconciliation. All new starts are
blocked while an uncertain entry remains; duplicate IDs and terminal rewrites
are rejected. Restore verified state first, inspect running jobs/server state,
and never automatically launch the possibly already-running action again.

Reconciliation outcomes:

- `completed`: authoritative complete result and quality evidence recovered; for
  upload, also independently retrieved bytes with the expected SHA256. A partial
  run is not completed. Whether a recovered run is analytically usable still
  depends on uninterrupted session/block context and all protocol quality gates.
- `excluded`: outcome unavailable, partial, invalid, or context interrupted. Keep
  evidence and exclude the affected comparison/block. Do not reconstruct counts
  or performance by joining fragments across restarts.
- `not_executed`: positive evidence the action never executed, not merely absence
  of a local result. Retain the original attempt and its evidence. Any later
  execution needs a new ID and follows the predeclared replacement policy.

```
python3 tools/evaluation_checkpoint.py /persistent/eval-ledger reconcile s01-b01-A --outcome excluded --evidence incident.json
```

## Uploads and external durability

At a frozen checkpoint boundary, stop the measured server/workload before packing
or uploading. Retain local immutable artifacts, their exact SHA256 and a manifest.
Start an upload intent with its destination and immutable object key in details:

```
python3 tools/evaluation_checkpoint.py /persistent/eval-ledger start upload-001 --kind upload --details 'approved destination; immutable key checkpoint-001' --artifact checkpoint-001.tar
# An authorized external uploader transfers exactly these bytes.
# Independently download that remote object; preserve receipt/key/version metadata.
python3 tools/evaluation_checkpoint.py /persistent/eval-ledger complete upload-001 --evidence receipt.json --downloaded retrieved-checkpoint-001.tar
```

The utility requires the retrieved bytes to hash-match the saved upload artifact;
it cannot determine whether the operator truly downloaded them or whether the
provider will retain them. A receipt alone does not establish durable upload, and
local fsync does not imply remote durability. Verify provider retention/versioning
and access separately. Do not embed secrets in evidence. Pack a settled ledger
snapshot plus all its referenced blobs, excluding mutable lock/temp files; the
upload intent for that archive necessarily lives in the subsequent ledger
revision. Preserve the remote object identifier/hash outside the VM so restoration
is possible after VM loss. Inspect/download remote state on an uncertain upload;
never automatically retry or overwrite the key. If verified, use `reconcile
--outcome completed --evidence ... --downloaded ...`; otherwise retain uncertainty
until authoritative inspection or record exclusion with a documented incident.

## Tested locally, still to test end-to-end

Ten standalone tests cover duplicate IDs/init, uncertain-action gating, explicit
reconciliation, terminal-state immutability, wrong/missing upload round-trip data,
ledger/blob corruption and missing blobs. SIGKILL is injected before file fsync,
before atomic replace, after replace and after directory fsync for intent and
completion transitions. A simulated external side effect followed by SIGKILL
leaves an uncertain upload requiring reconciliation. Surviving snapshots are
whole and hash-valid, with either the old or new operation state as appropriate.

These are real process-kill tests on this execution filesystem, not power-loss,
hypervisor-loss, storage-controller, network-partition or real-upload tests.
Before a long matrix, integrate the ledger with the actual driver and exercise
kill during warmup/work, result capture, archive creation, upload acknowledgment,
download verification and restoration onto a fresh execution directory. Verify
no duplicated external action, no inclusion of uncertain/partial runs, exact
manifest hashes, preserved exclusions and successful round-trip retrieval from
the actual authorized remote destination. Keep that test record separate from
performance observations. Until then, say local recovery primitive tested,
not automatic end-to-end crash recovery established.
