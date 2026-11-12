# VM A/A and client-resource diagnostic

This is not a publication evaluation, equivalence test, or acceptance gate. It
uses the RLBox-only server once per observation, not fake native/variant aliases.
The A/A labels denote identical arguments. CPU numbers identify allowed logical
or virtual CPUs, not dedicated physical cores.

## Frozen design

- Two original shapes: balanced_8c (8 clients, pipeline 10, 256-byte values,
  10,000 keys, 50% GET) and read_heavy_1k (8 clients, pipeline 16, 1 KiB values,
  10,000 keys, 95% GET), both cache_only.
- Each scenario has four Williams blocks, four configurations per block:
  count4-A and count4-B use CPUs 4-7; count5 uses 4-8; count1 uses CPU 4.
  The server uses CPUs 0-3. The client thread count stays eight in every case.
- Fixed schedule seed 2026111001 randomizes treatment labels, Williams row
  ordering and the global scenario/block ordering. Every configuration occurs
  once per position and every directed adjacency once per scenario.
- 20,000,000 measured operations plus 4,000,000 warmup operations per run.
  Same workload seed within each matched block, different seeds across blocks.
  No pilot adaptation. Intended approximately 15-second measured/3-second
  warmup fastest baseline is a planning estimate, not a required duration.
- 32 measured observations, 640M measured plus 128M warmup operations in total.
  Allow roughly 15-30 minutes plus remote checkpoint work; actual timing is
  recorded, and slow stress runs can take longer. Each client phase times out
  after 120 seconds, producing an uncertain block with retained evidence.
- Exact GET/SET counts are frozen by an excluded C++ counter using the bundled
  workload header. Parent must independently cross-check these using its
  separate counter before measurement. Main counts cannot be overridden.
- Count-only measurement; no latency, perf counters or privilege changes.
  The collector records raw stdout/stderr, warmup and measured stats, observed
  server mask, pre-launch client mask probe and direct client-exec runtime mask.
  Missing runtime affinity observation fails main collection. Short excluded
  smoke permits the client to exit before observation, retaining its probe.

## Freeze and execute

From the repository root (replace the fresh state path only):

    python tools/capacity_diagnostic.py init ../stage4-capacity-main --work ../stage2-server/memcached-build --correctness-summary ../stage3-deployment/summary.json --client-binary build/memcached_client

The initialization bundles and hashes all source, tools, binary inputs, expected
counts, plan and provenance. No benchmark is run. Inspect the plan, independently
verify expected counts and archive/upload the initial checkpoint before running.
Run with the bundled toolchain after initialization:

    python ../stage4-capacity-main/tools/capacity_diagnostic.py run ../stage4-capacity-main --max-blocks 1
    python ../stage4-capacity-main/tools/capacity_diagnostic.py export ../stage4-capacity-main ../stage4-capacity-block-01.tgz

The parent uploads the returned archive through the supported remote file flow,
verifies readback SHA-256, and keeps its transport receipt outside this frozen
state. Repeat only after verified upload, with a new archive name per block.
Compression and uploads occur only between blocks, after all servers stop.
The driver intentionally accepts exactly one block per invocation, with each
completed measured run separately fsynced and committed to the local ledger.

Portable restore, using the exact SHA-256 returned by export:

    python tools/capacity_diagnostic.py restore ../stage4-capacity-block-01.tgz ../stage4-capacity-restored --sha256 SHA256
    python ../stage4-capacity-restored/tools/capacity_diagnostic.py status ../stage4-capacity-restored

## Failures, preservation, and analysis

Never retry an uncertain observation. Inspect process identities and verify the
original collector, server and client stopped, then reconcile the attempt:

    python STATE/tools/capacity_diagnostic.py reconcile STATE ATTEMPT --reason 'Specific interruption and process verification' --confirm-no-active-processes

This excludes the entire matched block, including any completed observations.
All files remain hashed and retained. An interruption between completed runs
may leave no uncertain attempt: use `exclude-block STATE BLOCK --reason ...
--confirm-no-active-processes` instead. Do not resume a partial block as though
it were uninterrupted. No replacement block is allowed. Preserve failures,
excluded blocks and all order information in the final report.

Analyze all completed, nonexcluded blocks with descriptive paired ratios,
A/B variability, client and server CPU per operation, actual duration, order,
boot ID and invocation epoch. Each invocation epoch is a matched-block session,
not evidence of independent hosts or population replication. No independent-
session bootstrap, threshold acceptance, equivalence or publication claim.
Any +/-2% or other proposed band remains descriptive and unagreed.

## Excluded tests

`init ... --smoke-excluded` creates a distinct frozen phase with 20k/4k counts;
it must never be merged into main evidence. Unit tests are
`python tests/capacity_diagnostic.py`, with existing checkpoint regressions
`python tests/matrix_checkpoint.py` and `python tests/evaluation_checkpoint.py`.
