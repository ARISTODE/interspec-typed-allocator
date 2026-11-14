# YAML/libyaml Evaluation Results

The full libyaml parser processes a deterministic 1 MiB YAML document. Hosted CI values are reference measurements; publication numbers require the same driver on controlled hardware.

Reference commit: 8a3f278cbc0d62eacf229d5a8561f8db33cb6763

## Correctness and security

* Native, RLBox-only, tracking-only, and Extended-SP3 outputs match.
* Wrong-type, ordinary untracked, released, and excessive-extent scalar pointers are rejected before trusted copying.
* A live same-type substitution is accepted with unchanged contents, matching the current SP3 scope.
* The benchmark produces 512 scalar boundary values per parse.

## Performance

| Native median (ms) | RLBox median (ms) | Tracking median (ms) | InterSpec median (ms) | RLBox vs Native | Tracking vs RLBox | Validation vs Tracking | InterSpec vs RLBox | InterSpec vs Native |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7235.428 | 8699.998 | 8465.675 | 8495.308 | 20.55% | -3.19% | 1.29% | -4.01% | 15.98% |

Overheads are medians of paired per-repetition ratios. Negative values are not interpreted as speedups.

## Environment

{
  "commit": "8a3f278cbc0d62eacf229d5a8561f8db33cb6763",
  "platform": "Linux-6.18.44-fc-v470-x86_64-with-glibc2.39",
  "cpu_count": 4,
  "iterations": 1000,
  "repetitions": 15,
  "warmups": 2,
  "input_bytes": 1048576,
  "hosted_ci": "false",
  "measurement": "parse loop; sandboxed variants include per-iteration T-to-U input copy",
  "native_baseline": "native libyaml parser",
  "rlbox_baseline": "RLBox wasm2c with boundary scalar copy",
  "tracking_configuration": "typed scalar staging allocation, final SP3 check disabled",
  "security_configuration": "typed scalar staging allocation plus liveness/type/extent check",
  "rlbox_wasm2c_revision": "c4f18c48cea47421617f72ba5edc95c68aa85671",
  "libyaml_revision": "90a56d4500aa1a1798514c5cb55c3ad4cb095f94"
}
