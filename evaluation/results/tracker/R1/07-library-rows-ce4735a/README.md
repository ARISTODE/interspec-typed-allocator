# The eight library workloads after the switch-accessor fix

Why this run exists: in run 05 the RLBox-only binary of the hash port spent 21
instructions per boundary call in `WasmPort::switches()` that the InterSpec
binary did not spend, because the compiler inlined the accessor in one build
and not in the other (`../05-campaign-577528c/instr/memcached_hash/`:
RLBox-only 250.9, InterSpec with all policies off 230.9 instructions per
call). That favoured InterSpec in the rows with very short calls. `ce4735a`
makes the accessors `always_inline`. Only the six port programs use this
header, so this run repeats the port steps: builds and checks, alignment
check, `p7/`, `instr/`, `p6-ports/`. The four applications are not affected;
their numbers stay those of `../06-repetition-quiet-2d2c3af/`.

- Machine as in run 06 (same boot). Time: 2026-11-19 00:30 PT to 08:43 PT.
  Driver `campaign3c.sh`, log `campaign3c.log`, `steps.txt`: 30 steps, all
  with exit status 0, none repeated.
- Commit `ce4735a`; aligned builds (`compilers.txt`, `align-port-*.txt`: all
  functions checked start on a 64-byte boundary).
- Speed check before every timed step, as in run 06. The driver was stopped
  once while it waited at the check before `instr/ucl_libucl` and restarted
  with the check switched off for instruction counts, which do not depend on
  the load of the machine (note in `steps.txt`).

**The host was noisy during this run.** 122 checks before steps failed and
were waited out (about 6 hours of the 8), and the check right after the step
failed for 13 of the 16 timed steps. Each timed step started in a quiet
moment and takes 4 to 9 minutes, but it did not stay quiet. The medians are
from interleaved slices and agree with the instruction counts; the ranges are
wider than they would be on a quiet machine.

## The fix

Instructions per call of the hash function (`instr/memcached_hash/`):

| Configuration | Run 05 | This run |
|---|---:|---:|
| RLBox-only | 250.9 | 230.9 |
| InterSpec, all policies off | 230.9 | 230.9 |
| InterSpec | 202.4 | 202.4 |

The two binaries now do the same work when no policy is enabled. In time, all
off against RLBox-only is +1.2% (-5.1 to +4.1) (`p6-ports/memcached_hash/`).

## InterSpec against RLBox-only

15 repetitions of 30 interleaved slices; median, smallest and largest paired
ratio.

| Workload | Native | RLBox-only | InterSpec | Time | Instructions | Run 05, time |
|---|---:|---:|---:|---|---:|---|
| ffmpeg/libvpx (ms per frame) | 10.11 | 11.29 | 11.19 | -0.7% (-7.3 to +5.6) | -0.02% | -1.1% (-3.6 to +6.7) |
| magick/libpng (us per image) | 196.3 | 201.0 | 203.9 | +1.6% (-2.9 to +9.6) | -0.03% | -0.6% (-7.0 to +4.5) |
| memcached hash function (ns per call) | 8.9 | 21.4 | 20.1 | -6.7% (-8.5 to -3.4) | -12.34% | -13.3% (-14.9 to -9.0) |
| memcached hash table (ns per operation) | 173 | 226 | 216 | -4.3% (-7.2 to -2.1) | -3.66% | -2.7% (-6.2 to +0.4) |
| nginx/openssl (us per exchange) | 19.1 | 111.1 | 110.4 | -1.0% (-4.8 to +8.3) | -0.25% | -0.9% (-3.1 to +3.2) |
| ucl/libucl (us per iteration) | 6.24 | 7.27 | 7.62 | -0.0% (-5.6 to +7.5) | -0.49% | +0.2% (-3.3 to +5.4) |
| zip/libzip, queries (ns per query) | 91 | 117 | 127 | +8.6% (+3.9 to +14.6) | +12.57% | +6.3% (+2.5 to +10.2) |
| zip/libzip, listing (us per listing) | 663.7 | 571.1 | 602.5 | +5.2% (+1.2 to +8.8) | +4.63% | +5.2% (-0.6 to +9.4) |

- Four ranges include zero; the two memcached/hash rows are below zero and the
  two zip/libzip rows above. Geometric mean of the eight medians: +0.24%.
- Hash function: the advantage is half of what run 05 showed. The other half
  was the accessor.
- zip queries: 1,285.4 instructions under RLBox-only, 1,351.9 with all
  policies off (+66.5), 1,447.0 with all on (+161.6); the two checks are 95.1,
  as in run 05. The RLBox-only wrapper got 54 instructions shorter with the
  fix, so the cost against it is larger than in run 05.
- zip listing: 298,063 more instructions per listing of 1,000 entries.
- ucl/libucl: repeated counts differ by up to 7.8 million of about 620 to
  1,240 million, as before.
- Absolute times are 5% to 25% above those of run 05 in several rows (for
  example ucl 7.27 against 6.10 us), which fits the noisy host; the hash and
  zip rows are within 8%.

## Per-policy cost (`p6-ports/`)

`rendered-with-run-06/NUMBERS.md` has all rows (applications from run 06).
The combined cost of the three policies has its whole range on one side of
zero in one row, the hash function: -8.3% (-12.3 to -5.7), SP2 alone -8.0%.
Hash table: SP1 alone -5.9% (-7.6 to -1.4), SP3 alone +3.7% (-2.2 to +7.6),
all on -4.8% (-8.8 to +0.9). zip queries: SP3 alone +5.5% (+1.4 to +11.1),
all on +4.4% (-2.4 to +10.6), all on against RLBox-only +7.9% (+2.1 to
+14.9), all off against RLBox-only +4.0% (-2.9 to +8.2).

## Stored form

As in runs 05 and 06. `rendered-with-run-06/` is the output of
`tools/render_paper_performance.py` on a directory with the port steps of
this run, the application steps of run 06, and the instruction counts of
rsync and yaml and the memory runs of run 05; the paper's tables are made
from it.
