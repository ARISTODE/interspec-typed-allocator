# R1: cheaper object registry

Tracker item R1 in `EVAL_TRACKER.md`. All timings are from the Claude Code
cloud VM described in `evaluation/results/tracker/P1/` (4 virtual CPUs under
KVM, 16 GB, not a dedicated host), with nothing else running. Times in this
file are in PT.

| Directory | Content |
|---|---|
| `01-hash-table-diagnosis-12e8b9b/` | Why the memcached hash table stayed expensive after the first registry changes: cachegrind runs and a cycle-counter probe of the hash-table program at `12e8b9b`. |
| `02-campaign-12e8b9b-stopped/` | A first re-measurement at `12e8b9b`. I stopped it after the port timings, the instruction counts and the microbenchmarks, because the hash table still cost +27.9% and the diagnosis above pointed at a change of the runtime. It is kept as the measurement of that intermediate runtime; nothing in the paper cites it. |
| `03-campaign-930cb20/` | The complete re-measurement at `930cb20`: every timing item (P2 to P7, P9), the instruction counts of the ports (R3) and the registry microbenchmarks. `steps.txt` lists every step with start, end and exit status. |

## What changed in the runtime

Four commits between `ee90236` (before) and `930cb20` (after):

- `ef4602b`, `045c668`: the index of objects that T registers by address is a
  sorted block structure instead of a `std::map`, and tokens are resolved
  through a flat table.
- `12e8b9b`: the registry exists in a locked and in a single-threaded form. A
  program that tells RLBox that it uses its sandbox from one thread
  (`RLBOX_SINGLE_THREADED_INVOCATIONS`) tells the registry the same
  (`INTERSPEC_SINGLE_THREADED_REGISTRY`), and the registry then takes no lock.
  The two servers (memcached, nginx) keep the locked form.
- `930cb20`: handles. For an object of T that U only names and never
  dereferences, T hands U a handle instead of the address: an index into a
  table of T together with a generation that is never issued twice. Resolving a
  handle is one bounds check, one load and one comparison. The memcached hash
  table uses handles for the items it stores in U's table. Checked properties
  are the same as before: a handle resolves only to a live object of the
  expected type (`tests/runtime_handle_table.cpp`, and the security tests of
  the boundary, which pass at this commit).

## Registry operations, before and after

`03-campaign-930cb20/micro/`. Median of 15 runs, ns per operation, CPU 0.

P8 microbenchmark (`tools/run_runtime_microbench.py`). "Before" is the P8 run
at `f3dc8a5` (`../P8/01-vm-f3dc8a5/`), whose registry is the one of `ee90236`.

| Operation | Live objects | Before (`f3dc8a5`) | After, locked (`930cb20`) | After, single-threaded (`930cb20`) |
|---|---:|---:|---:|---:|
| Check of a pointer (`check_live`) | 2 | 22.5 | 24.2 | 5.9 |
| The lock alone (`shared_lock`) | 2 | 22.3 | 24.2 | (not taken) |
| Registration of an allocation (`allocate_from_site`) | 16,384 | 78.2 | 78.1 | 55.4 |
| Release (`release`) | 16,384 | 160.3 | 181.4 | 155.5 |

The locked form did not get faster: almost all of a check is the lock (24.2 of
24.2 ns), and the change leaves the lock in place where two threads can reach
the registry. The gain is in programs that use their sandbox from one thread,
where a check drops from 22.5 ns to 5.9 ns. Registration and release of
allocations of U changed little (the `std::map` of allocations is unchanged).

Objects of T registered by address and handles
(`evaluation/registry_external_bench.cpp`; `micro/ext/run/`, the three builds
interleaved; "before" is built from `ee90236`):

| Operation | Live objects | Before | After, locked | After, single-threaded |
|---|---:|---:|---:|---:|
| Resolve a token | 2 | 28.8 | 24.0 | 3.0 |
| Resolve a token | 20,000 | 304.2 | 29.1 | 10.0 |
| Remove one object and register another | 2 | 152.6 | 88.1 | 67.8 |
| Remove one object and register another | 20,000 | 789.9 | 300.6 | 249.2 |
| Resolve a handle | 2 | (no handles) | 22.6 | 1.7 |
| Resolve a handle | 20,000 | (no handles) | 25.6 | 3.0 |
| Remove one handle and issue another | 2 | (no handles) | 68.7 | 8.2 |
| Remove one handle and issue another | 20,000 | (no handles) | 75.5 | 10.2 |

With 20,000 live objects, which is the population of the hash-table workload,
resolving what U returns went from 304 ns to 3.0 ns, and replacing an entry
from 790 ns to 10.2 ns.

## The three workloads named in the item, timed again

P7 protocol (`tools/benchmark_ports.py --mode variants`, 15 repetitions of 30
interleaved slices, CPU 0). InterSpec against RLBox-only, median of the 15
paired ratios with the smallest and the largest. "Before" is P7 run 05
(`../P7/05-vm-8fc7020-rlbox-only-copies-everything/`). Raw samples:
`03-campaign-930cb20/p7/<boundary>/run/samples.csv`. Instructions per
iteration are from `03-campaign-930cb20/instr/` (callgrind, each count made
twice).

| Workload | Before, time | After, time | After, instructions |
|---|---:|---:|---:|
| memcached hash table | +146.7% (+135.7 to +153.3) | -3.0% (-8.4 to -1.4) | -3.6% |
| zip/libzip, metadata queries | +42.9% (+35.1 to +52.7) | +20.0% (+15.7 to +27.6) | +18.1% |
| magick/libpng | +7.3% (+3.7 to +14.1) | +1.5% (-4.6 to +7.9) | +0.02% |

- Hash table: the cost is gone. InterSpec is faster than RLBox-only in all 15
  repetitions. In the per-policy measurement (`p6-ports/memcached_assoc/`),
  SP1 alone saves 6.8% (-10.2 to -3.1), because a copy per operation is
  omitted, and SP3 alone costs +3.5% (-0.4 to +11.4).
- zip/libzip: the cost is halved and remains. A query takes 132 ns under
  RLBox-only and 157 ns under InterSpec; it passes two checks of pointers into
  U's allocations, and those still go through the `std::map` of allocations. A
  second measurement of the same binaries (per-policy protocol, `p6-ports/`)
  gives +23.4% (+17.3 to +30.8) against RLBox-only and +12.6% (+10.4 to
  +20.9) for SP3 alone against the same binary with all policies off.
- magick/libpng: the earlier +7.3% does not reproduce. The range includes
  zero, and the two builds execute the same number of instructions per image
  (1,977,488 against 1,977,978). R2 looks at the earlier binaries.

The other four port workloads at `930cb20`: memcached hash function -14.3%
(-17.9 to -11.5), ucl/libucl +3.2% (-3.8 to +8.4), nginx/openssl -0.7% (-5.5
to +2.9), ffmpeg/libvpx +2.1% (-1.7 to +5.6).

## Workflows at the changed commit

At `930cb20` (run ids on GitHub Actions): ci 44056214975, memcached-deployment
44056214912, nginx-deployment 44056215281, sp3-security-delta 44056214890, all
success. Also success: policy-switches 44056215801, p10-wasm2c-p7c
44056215132, yaml-libyaml-evaluation 44056214997.
`controlled-publication-evaluation` fails, as it does on every push since
before this item (not part of the item).

## Steps that failed in the campaign, and why

All are kept in `03-campaign-930cb20/`; none produced a number.

- `p3` (nginx throughput), first attempt: exit 1 within a second. The build
  script puts its output where `INTERSPEC_NGINX_WORK` says, not where its
  argument says, so the gate did not find the binaries. I linked the build
  directory to the expected place and ran the campaign driver a second time
  (`camp-chain.sh`); the second pass ran `p3` and the nginx memory runs. The
  directories `p3.failed-114934` and `p3.failed-165108` are the first attempt.
- `p6-apps/rsync`, `p6-apps/memcached`, `p6-apps/nginx`: exit 1 at the gate,
  before any timing (twice for rsync and memcached, once per pass). The
  RLBox-only binaries of these three applications report their policy as
  `boundary=<name>+sp3_fixed_at_compile_time`, because their registry is
  compiled out, and the gate of `tools/benchmark_policy_cost.py` compared
  against the plain name. The gate has been stale since `8fc7020`, when the
  RLBox-only configuration got explicit switches. Fixed in `00a20ec`; the
  three steps were run after the campaign on the same binaries (see `../R3/`).
- `p4.failed-115105` and `p5.failed-120022` are empty directories that the
  driver created before the step ran and then moved aside; `p4` and `p5`
  did not fail.
- Executables were removed from these directories; their SHA-256 are in the
  `removed-executables.sha256` files. Per-run directories of the servers and
  the callgrind profiles are packed in `.tar.gz` files next to their summaries.
