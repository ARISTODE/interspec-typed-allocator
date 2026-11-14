# P3: nginx/libpcre timing

Tracker item P3 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/` (4 virtual CPUs under KVM, 16 GB,
not a dedicated host), with nothing else running.

One run: `01-vm-0dfa03b-four-variants-4-and-8-threads/`.

## How it was run

- `tools/test_nginx_deployment.py` (the correctness gate), then
  `tools/benchmark_nginx.py --threads 4 8 --repetitions 15 --server-cpus 0-1
  --client-cpus 2-3`. The timing tool refuses to start unless the gate passed
  and the SHA-256 of the four binaries equals the gate's.
- Gate: 22 of 22 cases pass (`gate/summary.json`; the output of every case is
  in `gate/cases.tar.gz`).
- Binaries: built from commit `b1e0cbc` (`build-manifest.json`: nginx
  `1be0fb0`, PCRE 8.45 at `e67dabe`). No file of the nginx deployment changed
  between `b1e0cbc` and the commit of the run (`0dfa03b`).
- Workload: closed-loop `wrk`, 100 connections, 4 or 8 client threads, one
  request path that matches a regex location after 16 regex locations that do
  not match. Every response body is checked by the client script. nginx runs
  as one process (`workers 0`).
- A repetition measures the four variants once each in a seeded random order,
  each on a freshly started server: 3 s of warm-up, then a 30 s window.
  15 repetitions per thread count, 120 windows in total, none excluded.
- All 120 windows: every response validated, no connect, read, write, status
  or timeout error, window of at least 30 s (checked again in the script that
  wrote `PAIRED_RATIOS.md`).

## Result

Loss of throughput, median of the 15 paired ratios (smallest to largest).
Full table, also for server CPU time per request: `PAIRED_RATIOS.md`.

| Client threads | RLBox-only against native | Tracking against RLBox-only | InterSpec against RLBox-only | InterSpec against native |
|---:|---:|---:|---:|---:|
| 4 | +19.98% (+13.84 to +28.71) | +1.03% (-9.82 to +9.48) | +5.03% (-4.12 to +12.05) | +24.38% (+19.73 to +28.60) |
| 8 | +18.56% (+11.06 to +34.04) | -1.47% (-22.73 to +2.87) | +4.87% (-11.54 to +12.27) | +22.56% (+16.31 to +26.89) |

Median requests per second (native, RLBox-only, tracking without check,
InterSpec): 89,794, 72,164, 71,977, 69,108 with 4 threads; 79,399, 65,469,
67,048, 61,499 with 8 threads.

## Reading

- The sandbox costs about 20% of throughput on this workload; InterSpec's
  policies cost about 5% more. Server CPU time per request gives the same
  picture (+5.2% and +5.1% for InterSpec against RLBox-only).
- InterSpec is slower than RLBox-only in 12 of 15 repetitions with 4 threads
  and in 11 of 15 with 8 threads. The ranges include zero, so on this machine
  the 5% is an estimate with an uncertainty of several percent, not a
  resolved difference. The per-policy run on the same boundary
  (`../P6/README.md`) gives +5.5% (-1.7 to +11.8) for all policies against
  RLBox-only with a different window design, which agrees.
- This run uses one 30 s window per variant and repetition (the tool that
  existed before the noise analysis in `../P7/02-noise-probe/`). The ranges
  of about ±10% are those of this machine with server and client on all four
  virtual CPUs.
- VM numbers, not dedicated-host numbers; the paper has to describe the VM
  (P1) with them.
