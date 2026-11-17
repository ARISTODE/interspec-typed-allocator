# R3: cost without machine noise

Tracker item R3 in `EVAL_TRACKER.md`. Machine as in `../P1/`; times in PT.

## Where the parts are

| Part of the item | Raw output |
|---|---|
| Instruction counts, seven port measurements | `../R1/03-campaign-930cb20/instr/<boundary>/run/` (`counts.csv`, `TABLE.md`, profiles in `callgrind-profiles.tar.gz`) |
| Instruction counts, rsync/popt and yaml/libyaml | `01-vm-00a20ec/r3/rsync/run/`, `01-vm-00a20ec/r3/yaml/run/` (`tools/count_application_instructions.py`) |
| Per-policy timing, yaml/libyaml | `../R1/03-campaign-930cb20/p6-apps/yaml/run/` |
| Per-policy timing, rsync/popt, nginx/libpcre, memcached/bipbuffer | `01-vm-00a20ec/p6-apps/<application>/run/` |
| yaml/libyaml, four variants in interleaved slices | `01-vm-00a20ec/r3/yaml-sliced/run/` (`tools/time_binaries.py`) |

All binaries are those of the campaign at `930cb20`. The three per-policy steps
of `01-vm-00a20ec/` failed at the gate during the campaign because of a stale
comparison in `tools/benchmark_policy_cost.py` (see `../R1/README.md`); they
ran here with the tool of `00a20ec`. `steps.txt` lists every step of the
driver `after.sh` with its exit status (all 0).

## Instruction counts (InterSpec against RLBox-only)

Every count was made twice.

| Workload | RLBox-only | InterSpec | Difference | Largest difference between the two counts of a run (instructions of the whole run) |
|---|---:|---:|---:|---:|
| ffmpeg/libvpx, per iteration (12 frames encoded and decoded) | 121,498,845.0 | 121,479,462.2 | -0.02% | 0 |
| magick/libpng, per image | 1,977,488.0 | 1,977,978.0 | +0.02% | 0 |
| memcached hash function, per call | 250.9 | 202.4 | -19.33% | 0 |
| memcached hash table, per operation | 836.0 | 806.1 | -3.59% | 0 |
| nginx/openssl, per exchange | 912,623.3 | 910,215.7 | -0.26% | 12,154 |
| ucl/libucl, per iteration | 62,565.0 | 63,383.0 | +1.31% | 5,580,000 |
| zip/libzip, per query | 1,328.4 | 1,568.3 | +18.06% | 0 |
| rsync/popt, whole 194 MiB file sync | 6,283,899,642 | 6,284,488,630 | +0.01% | at most 30,051 |
| rsync/popt, option parsing only (whole run) | 2,933,985 | 3,025,962 | +3.13% | 0 |
| yaml/libyaml, per parse of the 1 MiB document | 122,488,254 | 122,385,822 | -0.08% | 0 |

The counts of a port are difference quotients between a run with N and one
with N/2 iterations. Two workloads do not repeat exactly: nginx/openssl (the
runs differ by up to 12,154 of about 1.4 billion instructions, which does not
change the digits shown) and ucl/libucl, whose runs differ by up to 5.6 million
of about 1.26 billion, so its +1.31% is uncertain by about one percentage point (the two
difference quotients of RLBox-only alone differ by 1.0%).

## Per-policy timing of the complete applications

Median of 15 paired ratios (smallest to largest); the first four columns are
against the same binary with all policies off.

| Application, workload | SP1 alone | SP2 alone | SP3 alone | All on | All on, against RLBox-only | All off, against RLBox-only |
|---|---:|---:|---:|---:|---:|---:|
| memcached/bipbuffer, watch_moderate | -1.1% (-5.1 to +3.6) | -0.6% (-4.3 to +1.4) | +0.3% (-3.6 to +3.5) | +1.1% (-5.6 to +2.9) | +1.1% (-4.1 to +8.5) | -0.3% (-4.9 to +7.4) |
| nginx/libpcre, 4 threads | -1.7% (-9.4 to +7.9) | -4.3% (-12.0 to +6.2) | +2.8% (-5.5 to +10.4) | -1.2% (-9.1 to +7.2) | +1.3% (-5.2 to +10.1) | +2.5% (-6.7 to +8.4) |
| rsync/popt, option parsing | +0.3% (-7.2 to +3.4) | -0.1% (-4.8 to +2.1) | +0.0% (-7.6 to +4.0) | +0.2% (-9.1 to +2.4) | +1.3% (-2.5 to +4.4) | +1.6% (-2.7 to +7.5) |
| rsync/popt, 194 MiB file sync | -0.3% (-3.3 to +3.1) | -0.2% (-3.7 to +2.6) | -0.6% (-2.1 to +3.7) | -0.6% (-3.2 to +1.6) | -0.1% (-2.0 to +1.9) | +0.5% (-1.1 to +3.3) |
| yaml/libyaml | no such policy | -1.3% (-5.8 to +8.0) | +0.7% (-5.2 to +6.5) | +0.5% (-4.9 to +8.1) | -2.4% (-16.4 to +5.6) | -3.2% (-12.1 to +5.2) |

Every range includes zero. The +9.8% for SP3 alone at nginx/libpcre of the
earlier P6 run (`../P6/`) does not reproduce (+2.8%, -5.5 to +10.4).

## yaml/libyaml in interleaved slices

The unsliced P5 measurement of the campaign was too noisy to bound anything
(+1.8%, -24.3 to +40.4). With 30 slices of 12 parses per repetition:

| Variant | ms per parse | Against RLBox-only |
|---|---:|---:|
| native | 7.40 | -19.2% (-22.5 to -16.4) |
| RLBox-only | 9.17 | |
| tracked-no-check | 9.03 | -2.4% (-8.3 to +2.0) |
| InterSpec | 9.16 | -1.2% (-6.6 to +6.5) |

RLBox-only against native: +23.7% (+19.7 to +29.0).
