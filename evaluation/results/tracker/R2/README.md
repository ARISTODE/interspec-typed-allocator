# R2: source of the magick/libpng cost

Tracker item R2 in `EVAL_TRACKER.md`. Machine as in `../P1/`; times in PT.

`01-vm-00a20ec/` (2026-11-17, driver `after.sh`, steps `r2/*` in `steps.txt`):

- `build-8fc7020/`: the magick/libpng port built again from commit `8fc7020`,
  the commit of the measurement that showed +7.3% (`../P7/05-vm-8fc7020-rlbox-only-copies-everything/`).
  The native binary has the SHA-256 of that measurement. The three sandboxed
  binaries do not (`build-8fc7020/run/binaries.sha256` against
  `../P7/05-*/binaries-png.sha256`): the build is not reproducible bit for bit
  from a different source directory. The comparison below is therefore with a
  rebuild of the earlier source, not with the earlier files.
- `time/`: seven binaries in one interleaved measurement (P7 protocol, 15
  repetitions of 30 slices of 700 images, CPU 0, `tools/time_binaries.py`):
  native, and RLBox-only, tracked-no-check and InterSpec from `930cb20` ("new")
  and from `8fc7020` ("old"). tracked-no-check is the InterSpec build without
  the checks: U's allocations go through the typed allocator and are recorded.
- `instr-8fc7020/`: instructions per image of the old binaries (callgrind,
  each count made twice, both equal).

## What the runs show

Paired ratios from `time/run/samples.csv` (median, smallest to largest):

| Comparison | Old build (`8fc7020`) | New build (`930cb20`) |
|---|---:|---:|
| InterSpec against RLBox-only | +4.7% (+1.7 to +12.0) | +1.4% (-5.0 to +3.7) |
| tracked-no-check against RLBox-only | +4.7% (-0.8 to +11.6) | -4.1% (-10.8 to +2.3) |
| InterSpec against tracked-no-check | +0.6% (-7.6 to +5.9) | +3.2% (-1.7 to +12.8) |

Old RLBox-only against new RLBox-only: -2.4% (-9.8 to +2.1). Old InterSpec
against new InterSpec: +1.7% (-4.4 to +5.9).

Instructions per image:

| Configuration | Old build | New build (`../R1/03-campaign-930cb20/instr/magick_libpng/`) |
|---|---:|---:|
| RLBox-only | 1,977,504 | 1,977,488 |
| tracked-no-check | 1,978,258 (+0.04%) | 1,977,787 (+0.02%) |
| InterSpec | 1,978,720 (+0.06%) | 1,977,978 (+0.02%) |
| InterSpec, all policies off | 1,979,276 (+0.09%) | 1,978,777 (+0.07%) |

Per image, the InterSpec build performs 2 registry allocations, 2 releases and
2 checks; libpng calls `malloc` and `free` in U 21 times each
(`../R1/03-campaign-930cb20/instr/magick_libpng/`, counted from the callgrind
profiles).

Reading:

- The rebuilt old binaries show a cost again, smaller than the first time
  (+4.7% instead of +7.3%), and the same cost without the checks. So the checks
  are not the source (+0.6%, range includes zero).
- The cost is not additional work: all variants of a build execute the same
  number of instructions per image to within 0.09%, 2 allocations per image
  cannot cost 8 microseconds, and the same source at `930cb20` shows no cost.
- What remains is a difference in running time between binaries that execute
  the same instructions. Between the seven binaries here it is up to about 6%
  (162 to 172 microseconds per image), and it does not follow the variant: the
  fastest binary is RLBox-only in the old build and tracked-no-check in the new
  one. I did not determine which property of the binaries causes it (placement
  of code or of data are the candidates; hardware counters are not available in
  this VM).

## What is still open for this item

- The item asks for "an RLBox-only build that links the typed allocator". The
  closest configurations measured so far are tracked-no-check (above) and the
  InterSpec binary with all policies switched off, which copies everything as
  RLBox-only does and records U's allocations
  (`../R1/03-campaign-930cb20/p6-ports/magick_libpng/`: +1.2% against
  RLBox-only, -2.9 to +7.6). The all-off configuration is not yet part
  of an interleaved measurement with the old binaries.
- zip/libzip difference between the two builds: see `../R4/README.md`; the
  difference there is real work (allocation records), not placement.
