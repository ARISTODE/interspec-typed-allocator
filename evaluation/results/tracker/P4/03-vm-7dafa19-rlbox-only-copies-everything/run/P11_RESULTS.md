# P11 RLBox wasm2c Performance Results

This file is mechanically rendered from the P11 four-way complete-rsync measurement stream.
Hosted CI values are reproducibility references only; use the same driver on controlled hardware for publication numbers.

Reference commit:

```text
7dafa197991e00625b639a24a56c94422ed6bd6a
```

Environment:

```text
commit=7dafa197991e00625b639a24a56c94422ed6bd6a
kernel=Linux 6.18.44-fc-v470 x86_64 GNU/Linux
cpu=Intel(R) Xeon(R) Processor @ 2.10GHz
logical_cpus=4
governor=unknown
turbo=unknown
cpu_affinity=0
repetitions=15
warmups=2
hosted_ci=false
measurement=complete process wall time via time.perf_counter_ns
native_baseline=native bundled popt
rlbox_baseline=rlbox_only
file_sync_workload=194 MiB local file, empty destination each measured invocation
tracking_configuration=tracked_no_check
security_configuration=extended_sp3
rlbox_wasm2c_revision=c4f18c48cea47421617f72ba5edc95c68aa85671
rsync_revision=7c20b077c980036a19587701cec320cc88e42a4a
note=hosted CI timings are reference measurements; publication values require a controlled host
```

| Workload | Native median (ms) | RLBox only median (ms) | Tracking/no-check median (ms) | Extended SP3 median (ms) | RLBox vs Native | Tracking/provenance | Validation | InterSpec vs RLBox | InterSpec vs Native |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| file_sync_194mb | 1365.052 | 1367.908 | 1356.543 | 1379.773 | 1.0% | -1.3% | 1.1% | 0.7% | 1.9% |
| local_dry_run | 25.550 | 31.041 | 27.280 | 45.627 | 5.2% | -0.0% | 0.9% | 0.8% | 7.9% |
| option_parse | 2.692 | 3.595 | 3.546 | 3.491 | 34.9% | -0.2% | 1.3% | 3.3% | 37.8% |

RLBox isolation is computed per repetition as `rlbox_only / native - 1`; tracking/provenance as `tracked_no_check / rlbox_only - 1`; validation as `extended_sp3 / tracked_no_check - 1`; InterSpec vs RLBox as `extended_sp3 / rlbox_only - 1`; and InterSpec vs Native as `extended_sp3 / native - 1`.
The component percentages are not additive because their denominators differ.
