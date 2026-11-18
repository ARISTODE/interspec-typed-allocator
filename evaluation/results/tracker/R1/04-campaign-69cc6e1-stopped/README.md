# Re-measurement at `69cc6e1`, stopped after 43 steps

Kept run; not used for the paper. Machine: Claude Code cloud VM (KVM guest,
4 vCPUs, Intel Xeon 2.10 GHz, 16 GB, Ubuntu 24.04, GCC 13.3). Driver:
`campaign2.sh`; step log with start, end and exit status: `steps.txt`.

- Commit `69cc6e1` holds the registry change of `e635d8d` (allocation records
  in a block index). Binaries are built without a fixed function alignment.
- All 43 finished steps have exit status 0: six port builds, the eight port
  workloads in four variants (`p7/`), their instruction counts (`instr/`),
  their per-policy runs (`p6-ports/`), the registry microbenchmarks
  (`micro/`), the libpng comparison of three builds (`r2/`), rsync/popt
  (`p4/`), yaml/libyaml (`p5/`), instruction counts of both and yaml in
  interleaved slices (`r3/`), and the nginx build.
- Not run: nginx timing (`p3`, interrupted, partial output in
  `p3.failed-044223/`), memcached, the per-policy runs of the four
  applications, memory.
- The container stopped twice during the run (notes in `steps.txt`); the
  driver was restarted each time and repeated the interrupted step.
- We stopped the run by hand because of `r3/yaml-sliced`: InterSpec +9.7%
  (+5.0% to +13.5%) against RLBox-only at an instruction count 0.08% lower.
  `../../R3/02-code-placement/` shows that this difference is the position of
  the library code relative to 64-byte boundaries. The next run builds every
  binary with `-falign-functions=64`.

Stored form: callgrind profiles of one directory are in
`callgrind-profiles.tar.gz`, the output directory of each port build is
`builds/<port>/run.tar.gz`, executables are removed and listed with their
SHA-256 in `removed-executables.sha256`.

InterSpec against RLBox-only in this run (15 repetitions, median and range of
the paired ratios; instruction counts from `instr/`):

| Port workload | Time | Instructions |
|---|---|---:|
| ffmpeg/libvpx | +0.6% (-8.7% to +3.6%) | -0.02% |
| magick/libpng | +0.7% (-5.2% to +10.6%) | -0.03% |
| memcached hash function | -13.3% (-16.0% to -8.2%) | -19.33% |
| memcached hash table | -2.1% (-5.5% to +0.3%) | -3.59% |
| nginx/openssl | -0.8% (-4.1% to +1.5%) | -0.26% |
| ucl/libucl | -0.7% (-8.5% to +5.0%) | +0.81% |
| zip/libzip queries | +9.5% (+4.9% to +16.8%) | +10.50% |
| zip/libzip listing | +5.9% (+2.0% to +10.2%) | +4.26% |
