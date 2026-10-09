# YAML/libyaml Evaluation Results

The full libyaml parser processes a deterministic 1 MiB YAML document. Hosted CI values are reference measurements; publication numbers require the same driver on controlled hardware.

Reference commit: cdef5b825e7c2db213127fcb9cb228270cf2667d

## Correctness and security

* Native, RLBox-only, tracking-only, and Extended-SP3 outputs match.
* Wrong-type, ordinary untracked, released, and excessive-extent scalar pointers are rejected before trusted copying.
* A live same-type substitution is accepted with unchanged contents, matching the current SP3 scope.
* The benchmark produces 512 scalar boundary values per parse.

## Performance

| Native median (ms) | RLBox median (ms) | Tracking median (ms) | InterSpec median (ms) | RLBox vs Native | Tracking vs RLBox | Validation vs Tracking | InterSpec vs RLBox | InterSpec vs Native |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4287.155 | 5813.376 | 5766.793 | 5810.707 | 34.77% | -0.37% | -0.09% | 0.01% | 34.29% |

Overheads are medians of paired per-repetition ratios. Negative values are not interpreted as speedups.

## Environment

{
  "commit": "cdef5b825e7c2db213127fcb9cb228270cf2667d",
  "platform": "Linux-6.17.0-1022-azure-x86_64-with-glibc2.39",
  "cpu_count": 4,
  "iterations": 1000,
  "repetitions": 15,
  "warmups": 2,
  "input_bytes": 1048576,
  "hosted_ci": "true",
  "measurement": "parse loop; sandboxed variants include per-iteration T-to-U input copy",
  "native_baseline": "native libyaml parser",
  "rlbox_baseline": "RLBox wasm2c with boundary scalar copy",
  "tracking_configuration": "typed scalar staging allocation, final SP3 check disabled",
  "security_configuration": "typed scalar staging allocation plus liveness/type/extent check",
  "rlbox_wasm2c_revision": "c4f18c48cea47421617f72ba5edc95c68aa85671",
  "libyaml_revision": "90a56d4500aa1a1798514c5cb55c3ad4cb095f94"
}

## Reference selection and variation

This report selects hosted workflow [37593628736](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37593628736), artifact 11471505440, with 15 paired repetitions and two warmups. The artifact ZIP checksum was verified against GitHub before importing the samples into `evaluation/results/yaml-libyaml/hosted-37593628736/`.

Paired InterSpec runtime change versus RLBox ranges from -6.44% to +4.66%, with a median of +0.01%. This variation does not establish a speedup or a precisely zero overhead.

The older five-repetition reference at 5061877 reported +2.48%. Its original CSV files remain under `evaluation/results/yaml-libyaml/`; they are not pooled with the newer run. See [SELECTED_EVALUATION_RESULTS.md](SELECTED_EVALUATION_RESULTS.md) for the current cross-application table.
