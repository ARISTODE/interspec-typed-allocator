# P11 RLBox wasm2c Performance Results

This file is mechanically rendered from the P11 four-way complete-rsync measurement stream.
Hosted CI values are reproducibility references only; use the same driver on controlled hardware for publication numbers.

Reference commit:

```text
2d2c3afb77b43ef9fb4054f4dfcb04a10b030752
```

Environment:

```text
commit=2d2c3afb77b43ef9fb4054f4dfcb04a10b030752
kernel=Linux 6.18.44-fc-v653 x86_64 GNU/Linux
cpu=Intel(R) Xeon(R) Processor @ 2.10GHz
logical_cpus=4
governor=unknown
turbo=unknown
cpu_affinity=unrestricted
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
| file_sync_194mb | 1343.501 | 1325.113 | 1323.316 | 1334.332 | -1.1% | -0.1% | 1.0% | 0.8% | 0.0% |
| local_dry_run | 42.603 | 43.644 | 23.855 | 23.705 | 2.6% | -15.0% | -0.6% | -1.9% | -42.7% |
| option_parse | 1.243 | 1.990 | 1.991 | 2.030 | 57.4% | 1.5% | 0.9% | 2.0% | 65.1% |

RLBox isolation is computed per repetition as `rlbox_only / native - 1`; tracking/provenance as `tracked_no_check / rlbox_only - 1`; validation as `extended_sp3 / tracked_no_check - 1`; InterSpec vs RLBox as `extended_sp3 / rlbox_only - 1`; and InterSpec vs Native as `extended_sp3 / native - 1`.
The component percentages are not additive because their denominators differ.
