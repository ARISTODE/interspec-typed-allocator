# Re-measurement at `577528c`, all binaries with aligned functions

The complete timing measurement after the second registry change
(`e635d8d`). This is the run that the paper's performance numbers come from.

- Machine: Claude Code cloud VM (KVM guest, 4 vCPUs, Intel Xeon 2.10 GHz,
  16 GB, Ubuntu 24.04, Linux 6.18, GCC 13.3). Not a dedicated host.
- Time: 2026-11-17 21:17 PT to 2026-11-18 08:55 PT.
- Driver: `campaign3.sh` (and `camp3-p2.sh` for memcached); log
  `campaign3.log`. `steps.txt` has every step with start, end and exit
  status: 55 steps, all with exit status 0, no step repeated.
- Commit: `577528c`. Its runtime (`include/`) is identical to `69cc6e1`, the
  commit of the stopped run in `../04-campaign-69cc6e1-stopped/`.
- Every compiler call goes through `scripts/aligned_compilers.sh`
  (`-falign-functions=64`; `compilers.txt`). Reason:
  `../../R3/02-code-placement/`. `align-*.txt` is the output of
  `tools/check_function_alignment.py` for every measured binary that contains
  sandboxed library code: all functions checked start on a 64-byte boundary
  (ports, rsync, yaml, nginx, memcached).
- Each step started when the 1-minute load average was below 0.30
  (`*.loadavg-before.txt`).

**The host became slower during this run.** From about 23:35 PT on
2026-11-17 the same program takes between 1.0 and 2.0 times its earlier time,
changing within seconds, with nothing else running in the machine. Steps
before that time (port builds, `p7/`, `instr/`, most of `p6-ports/`) are not
affected. For the steps after it, the comparison of InterSpec with RLBox-only
still holds, because the configurations are measured in interleaved slices
and the two binaries react alike; absolute times, throughputs and the
comparison with the native program are not those of a quiet machine. The
section "Host speed" below has the evidence and says which numbers are
affected.

`rendered/NUMBERS.md` is the output of
`tools/render_paper_performance.py . rendered` on this directory; the two
`.tex` files next to it are the table rows of the paper.

## InterSpec against RLBox-only

15 repetitions; median of the paired ratios with the smallest and the largest.
Positive means InterSpec takes more time per operation. RLBox-only copies
everything and has no registry. Instructions are counted under callgrind,
each count made twice.

Complete applications:

| Application, workload | Time | Instructions | Source |
|---|---|---:|---|
| memcached/bipbuffer, 1 client, 1:1 GET/SET | +0.4% (-6.8% to +5.2%) | | `p2/report/` |
| memcached/bipbuffer, 8 clients, 1:1 GET/SET | +0.2% (-8.3% to +9.5%) | | `p2/report/` |
| memcached/bipbuffer, read-heavy, 1 KiB values | +0.6% (-4.6% to +8.2%) | | `p2/report/` |
| memcached/bipbuffer, write-heavy | +3.1% (-3.4% to +14.5%) | | `p2/report/` |
| memcached/bipbuffer, one watcher, light load | +3.4% (-5.7% to +10.7%) | | `p2/report/` |
| memcached/bipbuffer, one watcher, moderate load | +3.7% (-2.7% to +9.2%) | | `p2/report/` |
| nginx/libpcre, `wrk`, 4 threads | -0.5% (-8.6% to +9.3%) | | `p3/run/timing/` |
| nginx/libpcre, `wrk`, 8 threads | +0.5% (-24.4% to +20.4%) | | `p3/run/timing/` |
| rsync/popt, 194 MiB file sync | -0.2% (-6.2% to +8.9%) | +0.00% | `p4/`, `r3/rsync/` |
| rsync/popt, option parsing only (3.5 ms) | +4.9% (-13.3% to +24.7%) | +0.10% | `p4/`, `r3/rsync/` |
| yaml/libyaml, 1 MiB document | +0.5% (-2.6% to +5.1%) | -0.08% | `r3/yaml-sliced/`, `r3/yaml/` |

Library workloads:

| Port workload | Time | Instructions | RLBox-only against native, time |
|---|---|---:|---|
| ffmpeg/libvpx | -1.1% (-3.6% to +6.7%) | -0.02% | +7.3% |
| magick/libpng | -0.6% (-7.0% to +4.5%) | -0.03% | -0.1% |
| memcached hash function | -13.3% (-14.9% to -9.0%) | -19.33% | +155.9% |
| memcached hash table | -2.7% (-6.2% to +0.4%) | -3.59% | +28.8% |
| nginx/openssl | -0.9% (-3.1% to +3.2%) | -0.26% | +497.0% |
| ucl/libucl | +0.2% (-3.3% to +5.4%) | -1.68% (see below) | +24.7% |
| zip/libzip, metadata queries | +6.3% (+2.5% to +10.2%) | +10.50% | +36.6% |
| zip/libzip, listing of 1,000 entries | +5.2% (-0.6% to +9.4%) | +4.26% | -12.4% |

Sources: `p7/<boundary>/run/samples.csv`, `instr/<boundary>/run/`.

What the tables say and do not say:

- Of the 19 rows, one has its whole range above zero (zip queries), one has
  its whole range below zero (hash function), and 17 have a range that
  includes zero. On this machine a difference below roughly 5% cannot be
  told from zero by timing; the instruction counts are the finer measure
  where they exist.
- memcached: three scenarios have a median above +3%. In those, 10 or 11 of
  the 15 repetitions are positive, and the ranges include zero. The same
  three scenarios gave -2.0%, +0.7% and +0.7% in the run at `930cb20`
  (`../03-campaign-930cb20/p2/report/`). The per-policy run on the
  moderate-watcher scenario (`p6-apps/memcached/`) gives +2.3% (-2.4% to
  +3.6%) for all policies against RLBox-only. We read this as "at most a few
  percent, not resolved by this measurement", not as zero.
- nginx at 8 threads on 4 virtual CPUs has a range of 45 points; it shows no
  difference and could not show one below 20%.
- ucl/libucl: its instruction counts are not repeatable (repeats of the same
  configuration differ by up to 4.9 million of about 460 to 930 million,
  about 1%), so the -1.68% is of the size of that variation. All other counts
  repeat exactly or to 0.002%.
- zip queries: 141 more instructions per query (1,339 to 1,480), 9 ns of
  127 ns. With all policies off the wrapper is 46 instructions longer than
  the RLBox-only wrapper; the two SP3 checks are the other 95.
- zip listing: 278,000 more instructions per listing of 1,000 entries
  (4.3%). Recording and releasing the 1,000 names costs 200 instructions per
  name (`allocate_with_hash_unlocked` 115, `release_unlocked` 85), the 2,000
  checks are inside the wrapper (215 per entry together with the selective
  copy), and the sandboxed `malloc` and `free` do 152,000 instructions less,
  because the recorded allocations are served by the typed allocator.
- zip listing, native: the native program takes 14% more time and executes
  23% more instructions than RLBox-only. The largest part is `getenv`
  (1.12 million instructions per listing) and `__offtime` (0.52 million):
  glibc's `mktime` reads the environment at every one of the 1,000 time
  conversions, and the C library inside the sandbox does not. The native
  column of this row is the cost of a different C library, not a baseline for
  the sandbox.

## Per-policy cost

`p6-ports/` and `p6-apps/`; `rendered/NUMBERS.md` has all 13 rows. Rows whose
combined cost has its whole range on one side of zero: hash function (-7.4%,
SP2 alone -7.5%), hash table (-3.9%; SP1 alone -5.7%, SP3 alone +4.0%), zip
queries (+5.4%; SP3 alone +5.4%, -2.5% to +11.6%).

## Registry operations

`micro/`, P8 tool, ns per operation, median (smallest to largest) of 15 runs,
CPU 0. "Before" is the registry of `930cb20`, built from the same benchmark
source.

| Operation | Live objects | Before, single-threaded | After, single-threaded | Before, locked | After, locked |
|---|---:|---|---|---|---|
| Check (`check_live`) | 2 | 8.57 (5.92 to 11.00) | 2.63 (2.50 to 5.38) | 25.87 (22.62 to 29.52) | 23.99 (22.30 to 31.29) |
| Registration (`allocate_from_site`) | 16,384 | 100.16 (58.55 to 147.13) | 31.99 (22.86 to 42.82) | 89.43 (72.56 to 243.16) | 53.85 (51.52 to 154.74) |
| Release (`release`) | 16,384 | 226.94 (155.82 to 310.06) | 9.65 (6.97 to 13.46) | 182.35 (165.30 to 256.31) | 35.12 (34.12 to 87.39) |

These four steps ran between 23:35 and 23:37 PT, when the host slowdown
described below began (a status check of the session also ran on the machine
at 23:36 PT). Their ranges are two to three times wider than in the same
steps of the stopped run (`../04-campaign-69cc6e1-stopped/micro/`: check 2.58,
registration 23.21, release 7.30 ns after; 6.06, 56.82, 152.65 ns before;
same registry code). The numbers of the stopped run are the ones to use until
the steps have been repeated on a quiet machine.

## libpng across four builds (`r2/time/`)

One interleaved run of 17 configurations, during the host slowdown: the
median slice of the reference configuration is 1.08 to 1.31 times the fastest
slice of its repetition (1.06 to 1.13 in the same step of the stopped run),
and the ranges are -16% to +20%. All medians are between -1.2% and +5.1% of
the aligned RLBox-only build. `../../R2/README.md` uses the same step of the
stopped run for the comparison of builds.

## Memory (`p9/`)

600 s under load per run, sampled every 5 s.

| Application | Variant | Peak RSS (MiB) | Sandboxes | Sandbox heap, all sandboxes (MiB) | Resident part of it, maximum (MiB) |
|---|---|---:|---:|---:|---:|
| memcached | native | 9.27 | 0 | | |
| memcached | RLBox-only | 33.74 | 12 | 35.75 | 0.93 |
| memcached | InterSpec | 35.03 | 12 | 47.25 | 0.52 |
| nginx | native | 4.34 | 0 | | |
| nginx | RLBox-only | 8.41 | 22 | 26.12 | 2.32 |
| nginx | InterSpec | 8.73 | 22 | 46.75 | 2.39 |

InterSpec's peak RSS is 1.29 MiB (memcached) and 0.32 MiB (nginx) above
RLBox-only. Before the registry change the two memcached variants had the
same peak RSS (33.20 MiB, `../../P9/README.md`); the block index and the
permanent block records are the difference.

## Host speed

What we saw:

- yaml/libyaml, RLBox-only, in `r3/yaml-sliced/` (00:37 PT): the fastest
  slice of a repetition is 9.7 to 14.3 ms per parse and the median slice 15.1
  to 18.4 ms. On 2026-11-17 in the afternoon the same build took 9.6 to 10.5
  ms in every slice (`../../R3/02-code-placement/3-aligned/`).
- The native servers are 10% to 15% below their throughput in the run at
  `930cb20`: nginx with 4 threads 71.7 against 82.1 thousand requests per
  second, memcached with 1 client 178 against 204 thousand operations per
  second. rsync's file sync takes 1.41 s against 1.27 s.
- The ratio of the median to the fastest slice of the RLBox-only
  configuration, per step, in the order in which the steps ran: `p7/` 1.04 to
  1.08 (as in the stopped run), `p6-ports/` 1.07 to 1.17 (rising), `r2/time/`
  1.20, `r3/yaml-sliced/` 1.30, `p6-apps/yaml/` 1.45.
- `host-speed/check-2026-11-18-0912PT.txt`, after the run, with the only other
  process of the machine stopped: ten runs of the yaml RLBox-only binary take
  0.124 to 0.256 s on each of the four CPUs; the native binary takes 0.103 to
  0.110 s. Switching address-space randomization off does not change it, and
  consecutive runs are alike, so it is a state that changes over seconds, not
  a property of a single run. The load average and the steal time of the
  machine do not show it. `tools/machine_quiet_check.py` is the check.

We do not know the mechanism (the machine is a guest on a shared host and has
no performance counters). Sandboxed code is slowed more than native code.

What it means for the numbers above:

- InterSpec against RLBox-only (time): usable. Both binaries are sandboxed and
  are measured in alternating slices; yaml, the most affected workload, gives
  +0.5% (-2.6% to +5.1%). The ranges of nginx and memcached are wider than in
  the run at `930cb20`.
- Instruction counts: not affected.
- RLBox-only against native, absolute times and throughputs of every step
  after 23:35 PT: too high or too low by an unknown amount of up to tens of
  percent. This concerns yaml (+64% against native here, +26% on the quiet
  machine), rsync, nginx, memcached, the libpng comparison of builds and the
  microbenchmarks. The eight port workloads of `p7/` are not concerned.
- Memory sizes: not affected.

The affected steps are repeated when the check finds the machine quiet; that
run is stored next to this one and both are kept.

## Stored form

Callgrind profiles of one directory are in `callgrind-profiles.tar.gz`; the
output directory of each port build is `builds/<port>/run.tar.gz`; the
per-run directories of the nginx timing are in `p3/run/timing-all-runs.tar.gz`
and those of memcached in `p2/report-runs.tar.gz`; executables are removed
and listed with their SHA-256 in `removed-executables.sha256`.
