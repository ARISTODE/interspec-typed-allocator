# P7: timing of the six ported boundaries

Tracker item P7 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/` (4 virtual CPUs Intel Xeon
2.10 GHz under KVM, 16 GB, not a dedicated host), all runs pinned to CPU 0,
nothing else running. All policies on, SP3 with the object registry.

| Directory | Result |
|---|---|
| `01-vm-d903d2f-one-run-per-repetition-noisy/` | Not used. One run of about one second per configuration and repetition. Paired ratios of the same pair ranged from -30% to +50%, and evidence files were being copied and committed while it ran. Kept as raw output. |
| `02-noise-probe/` | Why run 01 is not usable, and the design that is. The same binary varies by a factor of 1.3 to 1.6 between runs on this machine, in phases of one to two seconds. With 30 short interleaved slices per configuration and repetition, two copies of the same binary differ by -2% to +3%. |
| `03-vm-d9772b9-interleaved-slices/` | The measurement for ffmpeg/libvpx, magick/libpng, ucl/libucl, zip/libzip and the memcached hash call. Its nginx/openssl and hash-table runs have three variants and are replaced by run 04. |
| `04-vm-db7046a-four-variants-assoc-tls/` | The measurement for nginx/openssl and the memcached hash table, with the fourth variant (tracking without check, added in commit `0f05850`). Also holds the benign-parity runs of the two ports with four variants (20 of 20 and 24 of 24 pass) and the SHA-256 of the binaries. |

## Design

Tool `tools/benchmark_ports.py`, workloads `evaluation/performance/port_workloads.json`,
tables by `tools/render_timing_tables.py` from `samples.csv` only.

- A repetition is 30 rounds. A round runs every variant once, as a fresh
  process, in an order drawn from a seeded generator. One run (a slice) takes
  0.05 s to 0.3 s. The time of a variant in a repetition is the sum of its 30
  slices. 15 repetitions, so 450 slices per variant and boundary.
- The time of a slice is what the program reports for its workload loop.
  Process start, sandbox creation and input loading are outside it.
- Estimator: median over the 15 repetitions of the paired ratio (two variants,
  same repetition), with the smallest and the largest ratio.
- Correctness: before timing, every variant runs once and its result fields
  must equal the native program's (`gate.json`). Every timed slice is checked
  the same way; one mismatch or non-zero exit fails the measurement. All
  runs passed (`finish.json`: `all_timed_runs_correct`).
- The binaries of run 03 were built with `scripts/build_<x>_port.sh` on
  2026-11-14 after the last change to the port sources; the two of run 04 after
  commit `0f05850`, which added one binary per port and left the other
  binaries bit-identical. `run.json` of every run has the SHA-256 of what was
  timed.

## Result

Increase in time, median of 15 paired ratios (smallest to largest).

| Boundary | Work of one slice | RLBox-only against native | Tracking against RLBox-only | InterSpec against RLBox-only | InterSpec against native | Registry checks per slice |
|---|---|---:|---:|---:|---:|---:|
| ffmpeg/libvpx | 12 frames 352x288 encoded and decoded | +9.9% (+2.7 to +14.2) | +0.5% (-8.2 to +6.6) | +3.0% (-10.7 to +12.3) | +12.4% (-0.6 to +21.9) | 48 |
| magick/libpng | one image decoded and encoded, 700 times | -3.1% (-7.6 to +2.8) | +7.0% (-9.1 to +14.4) | +7.2% (-1.6 to +15.0) | +5.2% (-0.6 to +8.8) | 1,400 |
| memcached/hash, hash call | 8,000,000 hash calls | +131.7% (+118.3 to +143.2) | no registry | +0.3% (-3.5 to +5.0) | +129.0% (+121.7 to +152.0) | 0 |
| memcached/hash, hash table | 400,000 table operations on 20,000 keys | +17.4% (+12.9 to +26.5) | +76.2% (+68.4 to +91.2) | +168.5% (+140.4 to +174.8) | +211.9% (+204.0 to +225.2) | 277,994 |
| nginx/openssl | 1,500 TLS 1.3 round trips, 512-byte request, 4,096-byte response | +512.8% (+485.5 to +535.9) | -0.9% (-3.3 to +3.7) | +0.5% (-2.8 to +4.3) | +512.3% (+484.9 to +554.5) | 1,500 |
| ucl/libucl | one file parsed, two lookups, emitted, 20,000 times | +20.6% (+13.6 to +26.1) | +4.5% (+0.5 to +11.4) | +4.1% (-1.8 to +18.2) | +27.9% (+19.8 to +37.2) | 60,000 |
| zip/libzip | 1,000,000 entry stat and name calls | +44.3% (+36.3 to +52.0) | -2.5% (-6.5 to +5.3) | +41.2% (+33.1 to +46.5) | +99.1% (+89.8 to +117.7) | 2,000,000 |

Full tables: `03-…/TABLES.md` and `04-…/TABLES.md`.

## What the numbers say and what they do not

- Four boundaries show no cost of InterSpec over RLBox-only that this machine
  can resolve: ffmpeg/libvpx, nginx/openssl, the hash call and ucl/libucl
  have medians between +0.3% and +4.1% with ranges that include zero. For
  magick/libpng the median is +7.2% and the range reaches -1.6%; tracking
  alone has the same median (+7.0%), so what cost there is comes from the
  typed arena in U and not from the check.
- Two workloads show a clear cost, and both are loops of very cheap calls,
  so the fixed cost per call dominates.
  zip/libzip: about 113 ns per iteration without checks, two registry
  checks per iteration, +41%. That is about 23 ns per check. Tracking alone
  costs nothing measurable.
  memcached hash table: T registers every item it stores and unregisters it
  on delete, and checks every item handle that U returns. Registration alone
  costs +76%, registration and check +168%. One table operation takes about
  0.2 microseconds natively, so this is the worst case for a per-object
  registry.
- The cost of the sandbox itself (RLBox-only against native) is separate and
  often larger: +513% for the TLS round trip (the whole of OpenSSL compiled to
  WebAssembly) and +132% for the hash call.
- The memcached hash call has three variants, not four: U returns a number,
  there is no object to register, so there is no tracking variant. After the
  decision to move the hash table into U (I9) the hash table is the registry
  part of the memcached/hash boundary and has all four.
- The ranges are those of this VM. The ffmpeg/libvpx and magick/libpng ranges
  are about ±12%, wider than the noise probe's ±3%. I did not find the cause;
  the medians should be read with that range. These are not dedicated-host
  numbers; the paper has to describe the VM (P1) with them.
- The workloads are harness loops over one boundary, not application
  benchmarks. Application-level cost is P2 (memcached), P3 (nginx), P4 and
  P5.
