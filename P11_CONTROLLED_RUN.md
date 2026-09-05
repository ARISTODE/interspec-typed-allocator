# P11 Controlled-Hardware Run

The P11 implementation and hosted reference evaluation are complete. The last publication step is to execute the same three-way measurement on a machine whose scheduling and CPU policy are controlled well enough for paper-facing numbers.

## Preferred path

Use the manual GitHub Actions workflow `.github/workflows/p11-controlled-hardware.yml` with a dedicated Linux x86-64 self-hosted runner. The workflow deliberately does not install packages or change CPU power-management settings immediately before measurement. Prepare the host first, then leave it otherwise idle for the complete run.

Required build tools are `autoconf`, `automake`, `cmake`, `gcc`, `g++`, `git`, `make`, `python3`, and `taskset`, plus the popt development headers.

Before starting the measurement, keep the CPU frequency policy and turbo/boost state fixed for the whole session. The P11 driver records the state exposed by Linux but does not modify it.

Trigger the `p11-controlled-hardware` workflow with:

```text
cpu = 2
repetitions = 31
warmups = 3
```

The job runs all three complete-rsync configurations in one session:

```text
rlbox_only
tracked_no_check
extended_sp3
```

All recorded processes are pinned to the selected logical CPU. Execution order rotates through all six permutations of the three configurations.

## Publication-candidate gate

After measurement, `tools/validate_p11_controlled.py` checks that:

1. the run came from a self-hosted runner or a direct local execution rather than a GitHub-hosted runner;
2. at least 31 repetitions and 3 warmups were used;
3. CPU affinity was explicitly requested;
4. the pinned RLBox wasm2c and rsync revisions match the evaluated configuration;
5. both P11 workloads are present; and
6. every repetition contains one positive timing sample for each of the three modes.

The artifact contains `controlled-validation.txt`. `publication_candidate=PASS` means the mechanical protocol checks succeeded. Unknown governor or boost information is reported as a warning rather than silently treated as controlled; the paper should document the host policy when Linux does not expose it.

## Direct local alternative

The same run can be executed directly on a dedicated machine without GitHub Actions:

```bash
INTERSPEC_P11_REPETITIONS=31 \
INTERSPEC_P11_WARMUPS=3 \
INTERSPEC_P11_CPU=2 \
./scripts/run_p11_wasm2c_performance.sh p11-wasm2c-results

python3 ./tools/validate_p11_controlled.py \
  --environment p11-wasm2c-results/environment.txt \
  --summary p11-wasm2c-results/rsync-performance-summary.csv \
  --raw p11-wasm2c-results/rsync-performance.csv \
  --runner-environment local \
  --output p11-wasm2c-results/controlled-validation.txt
```

For the paper, preserve `rsync-performance.csv`, `rsync-performance-summary.csv`, `P11_RESULTS.md`, `environment.txt`, and `controlled-validation.txt` together. The raw CSV is the source of truth; the rendered table is derived from it.
