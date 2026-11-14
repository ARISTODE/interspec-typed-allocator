P11 RLBox wasm2c performance artifact

rsync-performance.csv
  Raw paired four-way complete-process samples.

rsync-performance-summary.csv
  Median/mean timing and paired tracking, validation, and total overhead.

P11_RESULTS.md
  Mechanically rendered table from the raw/summary data.

environment.txt
  Host, CPU, frequency-policy, affinity, repetition, and revision metadata.

p9b-prepare.log
  Complete preparation log for the typed wasm2c implementation.

The Native path uses the same pinned rsync revision and its bundled unmodified
popt. The RLBox-only path uses pinned uninstrumented bundled popt, ordinary
sandbox allocation, no typed arena, no PolicyRuntime initialization, no
allocation-site callback installation, and no final Extended-SP3 pointer check.
Dormant backend support code may remain linked, matching the P9a
runtime-path-baseline model.

The report workload includes a fresh-destination local synchronization of one
194 MiB file so the result is comparable in shape to the original InterSpec
rsync evaluation in addition to the option-parse and dry-run measurements.

Hosted CI timing is a reproducibility reference, not a publication result.
