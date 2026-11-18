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

## The all-off configuration next to the old binaries (2026-11-17)

`../R1/04-campaign-69cc6e1-stopped/r2/time/`: one interleaved measurement of
13 binaries and configurations (P7 protocol, 15 repetitions of 30 slices of
700 images, quiet machine): native, and for the builds of `8fc7020` ("old"),
`930cb20` ("mid") and `69cc6e1` ("new", the registry of `e635d8d`) the four
configurations RLBox-only, tracked-no-check, InterSpec, and InterSpec with
all policies off. The last one is the configuration the item asks for: its
wrapper copies everything, as RLBox-only does, and U's allocations go through
the typed allocator and are recorded.

Against the RLBox-only binary of the same build:

| Build | All policies off | tracked-no-check | InterSpec | InterSpec against all off |
|---|---:|---:|---:|---:|
| old (`8fc7020`) | +8.2% (+2.7 to +11.8) | +6.2% (-0.0 to +11.6) | +7.7% (+0.4 to +13.7) | -0.6% (-3.7 to +10.3) |
| mid (`930cb20`) | -3.7% (-8.2 to +3.0) | -6.4% (-11.8 to -3.9) | -4.0% (-7.6 to +5.2) | -0.6% (-4.1 to +4.0) |
| new (`69cc6e1`) | -1.2% (-7.1 to +2.1) | -0.6% (-4.7 to +2.1) | -0.9% (-4.0 to +4.9) | +0.4% (-2.2 to +12.9) |

All 13 against the new RLBox-only binary (`time/run/RATIOS.md`): twelve are
between -5.8% and +0.6%; the old RLBox-only binary is at -7.3% (-12.7 to
-2.3).

## Answer to the item

Which part of the +7.3% of the first measurement each candidate explains:

- **The checks: none.** InterSpec against the same binary with all policies
  off is -0.6%, -0.6% and +0.4% in the three builds, and 2 checks per image
  are about 5 ns of 190,000.
- **Selective copying: none.** The all-off configuration copies everything
  and shows the whole difference in the old build (+8.2%).
- **The typed allocator and the records: none that follows the allocator.**
  The old build shows +8.2% with the allocator linked and nothing else
  enabled, but the two later builds, which do the same 2 recorded allocations
  per image, show -3.7% and -1.2%. All builds execute the same number of
  instructions per image to within 0.09%.
- **What the +7.3% is:** the old RLBox-only binary is faster than every other
  sandboxed binary of the three builds, by about the amount in question
  (-7.3% against the new RLBox-only binary; old InterSpec is at -0.8%). The
  difference is a property of that one binary, not of a configuration.

What stays unexplained: why that binary is faster. For yaml/libyaml we showed
that the position of the library code relative to 64-byte boundaries changes
the time of one program by 13% (`../R3/02-code-placement/`); we did not make
the padding experiment for libpng, so for libpng this cause is likely and not
shown. With functions aligned to 64 bytes, as in all builds since `577528c`,
magick/libpng gives -0.6% (-7.0 to +4.5) at -0.03% instructions
(`../R1/05-campaign-577528c/`). That run also repeated the comparison of
builds with an aligned build added (`r2/time/`, 17 configurations); the host
was slow during that step and its ranges are -16% to +20%, so it adds
nothing to the table above.

zip/libzip difference between the builds: see `../R4/README.md`; there the
difference was real work (allocation records), and `e635d8d` removed most of
it.
