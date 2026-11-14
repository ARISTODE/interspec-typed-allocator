# P6: cost of each policy

Tracker item P6 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/` (4 virtual CPUs under KVM, 16 GB,
not a dedicated host), with nothing else running.

| Directory | Content |
|---|---|
| `01-vm-d9772b9-interleaved-slices/` | The four boundaries that had the switches first (I1 to I4): rsync/popt, yaml/libyaml, memcached/bipbuffer, nginx/libpcre. Tool `tools/benchmark_policy_cost.py`. Full tables in `TABLES.md`. The run directories of the two servers are in `runs.tar.gz`. |
| `02-vm-5935321-ports-interleaved-slices/` | The six ported boundaries (seven workloads; memcached/hash has the hash call and the hash table). Tool `tools/benchmark_ports.py --mode policies`. Full tables in `TABLES.md`. |

The two tables below are produced by `tools/render_policy_cost_summary.py` from
the `samples.csv` files. Only the row labels were rewritten by hand.

## Design

- One InterSpec binary per boundary. The policies are selected at run time
  with `INTERSPEC_SP1`, `INTERSPEC_SP2`, `INTERSPEC_SP3`. Six configurations:
  all off, each policy alone, all on, and the RLBox-only binary for reference.
  With a policy off the wrapper does what a wrapper without that policy
  would do: SP1 off copies the field in, SP2 off copies U's version back,
  SP3 off leaves only the sandbox confinement check.
- The gate before timing checks, for every configuration, that the result
  equals the RLBox-only result and that the policy report printed by the
  wrapper matches the switches (`gate.json`).
- 15 paired repetitions. A repetition consists of rounds; a round measures
  every configuration once in a seeded random order. Rounds per repetition:
  rsync option parsing 100, rsync file sync 8, yaml 30, the two servers 6
  windows of 2 s after 1 s of warm-up, the ports 30. The value of a
  configuration in a repetition is the sum of its slices (time) or the mean of
  its windows (throughput). Why: `../P7/02-noise-probe/README.md`.
- Estimator: median over the repetitions of the paired ratio, with the
  smallest and largest ratio. "Cost" is the relative increase in time per
  unit of work.
- Every measurement validated its result; none failed (`finish.json`).

## Cost against the same binary with all policies off

Median (smallest to largest) of 15 paired ratios. The last two columns are
against the RLBox-only binary.

| Boundary, workload | SP1 alone | SP2 alone | SP3 alone | All on | All on, against RLBox-only | All off, against RLBox-only |
|---|---:|---:|---:|---:|---:|---:|
| rsync/popt, option parsing (about 3 ms per slice) | -0.7% (-4.9 to +1.6) | -1.3% (-3.0 to +2.3) | -0.0% (-3.6 to +3.9) | -0.4% (-2.8 to +5.4) | +1.6% (-0.8 to +7.4) | +2.1% (-1.3 to +5.3) |
| rsync/popt, 194 MB file sync | +0.1% (-2.1 to +2.7) | -0.6% (-2.6 to +2.8) | +0.0% (-1.9 to +2.5) | +0.1% (-2.1 to +3.2) | +0.1% (-2.6 to +1.9) | -0.1% (-2.2 to +0.8) |
| yaml/libyaml, 1 MB document parsed 12 times | no such policy | -0.7% (-6.0 to +9.5) | -0.9% (-7.4 to +9.0) | -0.7% (-5.3 to +6.4) | -2.7% (-8.8 to +1.9) | -2.6% (-11.2 to +3.5) |
| memcached/bipbuffer, watch_moderate (throughput) | +2.1% (-4.6 to +6.2) | +0.8% (-5.0 to +3.4) | +2.4% (-4.4 to +5.6) | +1.7% (-2.9 to +7.0) | +1.8% (-2.3 to +5.4) | +0.2% (-5.4 to +4.1) |
| nginx/libpcre, regex location, 4 client threads (throughput) | -2.4% (-12.9 to +8.9) | -3.7% (-10.3 to +8.5) | +9.8% (-4.4 to +18.6) | +0.5% (-6.8 to +9.1) | +5.5% (-1.7 to +11.8) | +3.8% (-4.5 to +13.9) |

yaml/libyaml has no SP1 field.

| Boundary, workload | SP1 alone | SP2 alone | SP3 alone | All on | All on, against RLBox-only | All off, against RLBox-only |
|---|---:|---:|---:|---:|---:|---:|
| ffmpeg/libvpx | +0.2% (-6.9 to +8.7) | +1.4% (-6.5 to +9.9) | +1.0% (-6.6 to +6.4) | -1.4% (-5.3 to +7.2) | +0.1% (-9.8 to +6.3) | +1.3% (-9.1 to +6.8) |
| magick/libpng | -0.0% (-3.8 to +3.5) | -0.1% (-5.5 to +6.2) | -1.1% (-6.4 to +5.7) | -1.8% (-4.6 to +4.7) | +4.7% (-3.2 to +11.5) | +6.6% (-1.5 to +13.5) |
| memcached/hash, hash call | -0.0% (-4.4 to +7.9) | -7.2% (-14.1 to -4.0) | +0.1% (-3.6 to +6.3) | -6.3% (-13.3 to -2.8) | +0.5% (-2.4 to +3.0) | +8.9% (+3.1 to +12.6) |
| memcached/hash, hash table | -6.2% (-12.7 to -1.0) | -1.8% (-6.7 to +3.8) | +155.8% (+144.5 to +163.2) | +143.2% (+132.2 to +156.9) | +170.1% (+147.1 to +183.2) | +10.3% (+0.8 to +18.8) |
| nginx/openssl | +1.1% (-2.7 to +3.5) | -0.1% (-2.9 to +6.3) | -0.0% (-4.3 to +2.9) | -0.4% (-5.9 to +7.7) | +0.5% (-3.9 to +4.1) | +0.6% (-3.6 to +4.9) |
| ucl/libucl | -2.2% (-6.5 to +9.8) | -2.7% (-10.1 to +6.5) | +0.6% (-10.0 to +5.5) | +0.5% (-5.6 to +5.5) | +5.4% (-3.0 to +12.9) | +5.4% (-2.6 to +10.9) |
| zip/libzip | +0.6% (-4.3 to +6.0) | -0.4% (-5.3 to +4.1) | +30.2% (+20.0 to +33.4) | +27.7% (+20.4 to +35.5) | +42.0% (+36.9 to +51.0) | +11.0% (+7.3 to +17.6) |

## Reading

- On rsync/popt, yaml/libyaml and memcached/bipbuffer no policy, alone or
  together, has a cost that this machine can resolve: all medians are
  between -1.3% and +2.4%, all ranges include zero.
- nginx/libpcre: SP3 alone costs +9.8% (-4.4 to +18.6), and it is slower than
  the RLBox-only binary in all 15 repetitions (+11.3%, +4.5 to +22.3). All
  three policies together cost +0.5% (-6.8 to +9.1). The wrapper explains
  the order (`integration/nginx_server/bridge.cpp`, `exec`): with SP1 off the
  output vector is copied in and with SP2 off the subject is copied back, and
  with SP3 on each of these copies passes its own registry check. So SP3
  alone performs up to four registry checks per `pcre_exec` (three when the
  pattern does not match) and all policies together up to two (one). The request passes 17 regex locations. nginx is the noisiest
  of the workloads (about ±10%): server and client together use all four
  virtual CPUs.
- The ports: the cost is in SP3 where there is one. zip/libzip +30.2%, the
  memcached hash table +155.8%; both are loops of very cheap calls (see
  `../P7/README.md`). The other five workloads show nothing for any policy
  alone.
- SP1 and SP2 can save time, because they remove a copy. memcached hash call:
  SP2 alone -7.2% (-14.1 to -4.0), since the key is not compared and copied
  back after each of the 8,000,000 calls. Hash table: SP1 alone -6.2%
  (-12.7 to -1.0).
- The InterSpec binary with all policies off is slower than the RLBox-only
  binary on some ports (zip/libzip +11.0%, hash table +10.3%, hash call +8.9%).
  The RLBox-only binary is built from the same source with the registry
  compiled out and runs with SP1 and SP2 on, so part of this is the copies
  that SP1 and SP2 save (the hash call). For zip/libzip I did not attribute
  it: neither SP1 nor SP2 alone changes the time there.
- These are VM numbers with the ranges shown, not dedicated-host numbers.
