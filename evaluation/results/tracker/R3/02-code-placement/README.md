# yaml/libyaml: a 10% time difference that is code placement

Measured on 2026-11-17 (PT) on the Claude Code cloud VM (KVM guest, 4 vCPUs,
Intel Xeon 2.10 GHz, 16 GB, Ubuntu 24.04, GCC 13.3). Runs are pinned to CPU 0.
Each table is `tools/time_binaries.py` with 5 repetitions of 30 interleaved
slices, 12 parses of the 1 MB document per slice; the percentages are the
median, smallest and largest paired ratio.

## What was observed

The re-measurement at `69cc6e1` (the commit after the registry change
`e635d8d`) gave for yaml/libyaml, 15 repetitions
(`campaign-69cc6e1-yaml-sliced-RATIOS.md`):

| Configuration | Against RLBox-only |
|---|---|
| tracked, no check | +9.8% (+5.9% to +14.8%) |
| InterSpec | +9.7% (+5.0% to +13.5%) |

The same workload at `930cb20` gave -1.2% (-6.6% to +6.5%) for InterSpec. The
instruction count of InterSpec at `69cc6e1` is 0.08% below RLBox-only. This
result is kept; it is not used for the paper because of what follows.

## What it is

1. **It is a property of the binary, not of the checks.**
   `1-old-and-new-binaries/`: the InterSpec binary of `69cc6e1` is 9% to 13%
   slower than the RLBox-only binary of the same commit with the checks on,
   with tracking only, and with all three policies switched off. The InterSpec
   binary of `930cb20` is not slower in any of the three settings.
2. **The work is the same.** `cachegrind/`: the two InterSpec binaries execute
   1,490,663,297 and 1,490,728,392 instructions and have 1,198,369 and
   1,199,936 first-level data-cache misses in the cache simulation. 91.6% of
   the instructions are in two functions of the sandboxed library
   (`yaml_parser_fetch_more_tokens`, `yaml_parser_update_buffer`); the registry
   is not on the hot path of this workload (512 scalars per parse).
3. **It follows the position of the library code.** `2-padding/`: we linked
   the same object files with a padding object of 0, 16, 32 or 48 bytes in
   front of the library. Nothing else differs between the copies.

   | Program | Padding | Start of `update_buffer` modulo 64 | Against the RLBox-only binary of the campaign |
   |---|---:|---:|---|
   | RLBox-only (campaign binary) | | 48 | 0 |
   | InterSpec (campaign binary) | | 0 | +11.1% (+6.2% to +13.8%) |
   | RLBox-only | 0 | 0 | +11.3% (+6.1% to +15.5%) |
   | RLBox-only | 32 | 32 | -2.1% (-8.2% to -0.1%) |
   | InterSpec | 0 | 16 | +3.2% (-6.7% to +3.7%) |
   | InterSpec | 16 | 32 | -3.6% (-7.5% to +3.1%) |
   | InterSpec | 32 | 48 | -0.5% (-3.8% to +6.2%) |
   | InterSpec | 48 | 0 | +7.3% (+5.4% to +16.5%) |

   Two links of the RLBox-only program that differ by 32 bytes of padding
   differ by 13% in time. Every copy in which the function starts on a 64-byte
   boundary is slow, whichever configuration it is. The addresses and the
   checksums of all binaries are in `hot-function-addresses.txt`.

The trusted side of the two configurations has a different size (the registry
is compiled out of RLBox-only), and it is linked before the library. The
registry change of `e635d8d` changed that size by a number of bytes that moved
the library of the InterSpec binary from a fast to a slow position.

## What we changed in the method

All measured binaries are now built with `-falign-functions=64`
(`scripts/aligned_compilers.sh`; `tools/check_function_alignment.py` checks
the result). The library functions then start at the same position relative to
a 64-byte boundary in every configuration. `3-aligned/`:

| Configuration (aligned build) | Against aligned RLBox-only |
|---|---|
| tracked, no check | +0.1% (-5.0% to +3.8%) |
| InterSpec | -1.0% (-4.1% to +2.7%) |
| InterSpec, all policies off | +0.1% (-6.1% to +2.9%) |
| native | -20.6% (-25.1% to -19.6%) |

In the two aligned binaries the two hot functions are at the same addresses
(`0x1a280`, `0x20f00`). For this library the aligned position is the slow one:
the unaligned RLBox-only binary of the campaign is 9.2% faster than the
aligned one. The comparison between configurations is what the alignment makes
fair; absolute times of this workload are higher than in earlier runs.
`3-aligned/yaml-script-performance-summary.csv` is the timing that the yaml
script itself runs on the aligned build (15 repetitions, not interleaved):
InterSpec is 0.5% above RLBox-only at the median.

## Limits

- The alignment fixes the start of each function, and with it every loop
  inside the function. It does not fix the position of the trusted code, which
  differs between configurations by design.
- We did not determine which processor mechanism makes the aligned position
  slow for this loop. The VM has no hardware performance counters.
- 5 repetitions per table. The complete re-measurement with aligned builds has
  15.
