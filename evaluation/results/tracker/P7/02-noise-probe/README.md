# Run-to-run variation of this machine (2026-11-14)

Why the first P7 run (`../01-…`) is not used. Each line below is the same
binary and the same workload, started again and again with nothing else
running (`noise_probe.py`; `zip-native`, 6,000,000 and 36,000,000 iterations).

| Run length | CPU | Runs | Median (ms) | Min (ms) | Max (ms) | Max/min | Steal reported, median |
|---|---|---:|---:|---:|---:|---:|---:|
| about 0.5 s | 0 | 12 | 517.3 | 431.0 | 690.5 | 1.60 | 1.8% |
| about 0.5 s | 1 | 12 | 448.7 | 419.0 | 628.0 | 1.50 | 0.0% |
| about 0.5 s | 2 | 12 | 623.2 | 480.7 | 667.5 | 1.39 | 0.0% |
| about 0.5 s | 3 | 12 | 471.9 | 421.3 | 534.4 | 1.27 | 0.0% |
| about 3 s | 0 | 8 | 3291.4 | 2681.1 | 3761.0 | 1.40 | 0.3% |
| about 3 s | 1 | 8 | 2982.7 | 2593.1 | 3231.5 | 1.25 | 0.4% |
| about 3 s | 2 | 8 | 2822.3 | 2552.0 | 3384.7 | 1.33 | 0.4% |
| about 3 s | 3 | 8 | 3135.1 | 2693.1 | 3865.1 | 1.44 | 0.3% |

The speed of the machine changes by a factor of 1.3 to 1.6 between runs, on
every CPU, for short and for longer runs, and the guest sees almost no steal
time. A series of 240 runs of 0.1 s on CPU 1 showed slow phases lasting about
one to two seconds (autocorrelation 0.73 at the next run, 0.42 four runs
later, 0.01 at 32 runs).

`series-1440-slices-cpu0.json` holds 1,440 consecutive runs of 0.1 s
(1,200,000 iterations) on CPU 0, in milliseconds. Treating the runs as four
alternating configurations (run i belongs to configuration i mod 4) and
comparing the first two, which are the same binary, gives the spread a harness
would report for a true ratio of 1:

| Slices per configuration and repetition | Repetitions available | Median ratio | Smallest | Largest |
|---:|---:|---:|---:|---:|
| 1 | 360 | 1.001 | 0.646 | 1.516 |
| 5 | 72 | 1.007 | 0.803 | 1.089 |
| 10 | 36 | 1.009 | 0.885 | 1.058 |
| 20 | 18 | 1.007 | 0.955 | 1.043 |
| 30 | 12 | 0.996 | 0.979 | 1.029 |

So a repetition made of 30 interleaved slices, summed per configuration,
brings the spread of a paired ratio from about -35%/+52% to about -2%/+3%.
The harnesses were changed accordingly (commit `d9772b9`).
