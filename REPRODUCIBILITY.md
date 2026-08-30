# Reproducibility

This repository pins the external source revisions used by the RLBox + NaCl proof and provides a reproducible path from policy inference through P8 paper-facing evidence and release packaging.

## 1. Required environment

The lightweight runtime, policy generation, P6 evaluation, and deterministic P8 report use a C++17 compiler, CMake, Python 3, and pthread support.

The full RLBox + NaCl integration is tested in repository CI with Ubuntu 20.04 and installs the build dependencies listed in `.github/workflows/ci.yml` before invoking the integration and P8 measurement drivers.

## 2. Pinned external revisions

RLBox NaCl sandbox:

```text
repository: https://github.com/PLSysSec/rlbox_nacl_sandbox.git
commit: 0dd15342c86c0625c7c2ed7762a13feb524252d7
```

NaCl sandbox compiler:

```text
repository: https://github.com/PLSysSec/nacl_sandbox_compiler.git
commit: f274515ab22441ea6b4e937e519ace851fac308f
```

Rsync source used by the real popt boundary:

```text
repository: https://github.com/RsyncProject/rsync.git
commit: 7c20b077c980036a19587701cec320cc88e42a4a
```

The RLBox and NaCl revisions are also recorded in `backends/rlbox_nacl/manifest.json`. Real-boundary source revisions are recorded in the integration manifests consumed by the P7c/P8 report. The integration scripts refuse to treat arbitrary upstream revisions as equivalent to the evaluated configuration.

## 3. Core correctness

```bash
cmake -S . -B build
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

This runs the mechanism PoC, runtime hardening tests, policy generation tests, P6 security evaluation, P7c report checks, and P8 report/rendering unit tests.

## 4. Source policy inference

The CodeQL CI job regenerates checked-in policy snapshots from source and requires exact equality. It covers the runtime policy, rsync/popt, memcached/bipbuffer, nginx/libpcre, and yaml/libyaml integration policies.

When CodeQL is available on `PATH`, the same repository scripts can be run directly:

```bash
./scripts/run_policy_inference.sh
./scripts/run_rsync_popt_policy_inference.sh
./scripts/run_memcached_bipbuffer_policy_inference.sh
./scripts/run_nginx_libpcre_policy_inference.sh
./scripts/run_yaml_libyaml_policy_inference.sh
```

A mismatch is a failure rather than an automatic policy update. This makes policy drift visible for review.

## 5. P6 security and trusted-metadata runtime evaluation

```bash
chmod +x scripts/run_p6_evaluation.sh
./scripts/run_p6_evaluation.sh p6-results
```

The result directory contains the exact security matrix, runtime measurements, test output, commit identifier, compiler version, CMake version, kernel description, and configured benchmark iteration count.

For more stable metadata timing measurements, use a dedicated machine and raise the iteration count, for example:

```bash
INTERSPEC_BENCH_ITERATIONS=2000000 ./scripts/run_p6_evaluation.sh p6-results
```

Do not compare absolute nanosecond values from unrelated machines as if they were controlled experiments.

## 6. P8 deterministic evidence

```bash
chmod +x scripts/run_p8_evaluation.sh
INTERSPEC_BENCH_ITERATIONS=100000 ./scripts/run_p8_evaluation.sh p8-results
```

This reuses the P6 security/runtime path, requires the P7c generalization report to be complete, and produces the machine-readable P8 completion and automation records. The key outputs are `p8-deterministic.json`, `p8-automation.csv`, `p7c-generalization.json`, and the inherited P6 security/runtime CSV files.

A completed deterministic report has `deterministic_complete` set to `true`. Release packaging rejects an incomplete report.

## 7. Full RLBox + NaCl integration and P8 paired measurements

```bash
chmod +x scripts/run_rlbox_nacl_poc.sh \
  scripts/run_yaml_libyaml_rlbox_extension.sh \
  scripts/write_p8_rlbox_environment.sh \
  scripts/run_p8_rlbox_evaluation.sh

INTERSPEC_P8_BOUNDARY_ITERATIONS=20000 \
INTERSPEC_P8_APP_REPETITIONS=9 \
./scripts/run_p8_rlbox_evaluation.sh p8-rlbox-results
```

The driver clones the pinned RLBox, NaCl, rsync, and boundary source revisions as required, applies the packaged backend, regenerates typed allocation policy artifacts, builds the sandboxed integrations, executes the synthetic and real-boundary regressions, and produces paired boundary/application timing evidence.

The paired baseline is `tracked_no_check`: sandboxing, typed allocation/provenance, policy registration, and marshalling remain enabled, while only the final T-side Extended-SP3 pointer acceptance check is bypassed. Therefore these measurements quantify incremental validation overhead, not total Extended-SP3 overhead relative to plain RLBox.

Network access is required because the external repositories are cloned during the run. Hosted CI timings are reproducible reference measurements. Final publication timing numbers should be regenerated on controlled hardware with the same output format.

## 8. Install and external consumer test

```bash
cmake -S . -B build-install -DCMAKE_BUILD_TYPE=Release
cmake --build build-install --parallel
cmake --install build-install --prefix "$PWD/stage"

cmake -S examples/consumer -B build-consumer \
  -DCMAKE_PREFIX_PATH="$PWD/stage"
cmake --build build-consumer --parallel
./build-consumer/interspec_runtime_consumer
```

This verifies that the installed public header and exported `interspec::runtime` CMake target can be consumed outside the source tree.

## 9. Build the complete research preview archive

The release archive intentionally requires both P8 evidence directories so a green packaging job cannot silently publish a pre-P8 artifact.

```bash
./scripts/run_p8_evaluation.sh p8-results
./scripts/run_p8_rlbox_evaluation.sh p8-rlbox-results

INTERSPEC_P8_EVAL_DIR="$PWD/p8-results" \
INTERSPEC_P8_RLBOX_DIR="$PWD/p8-rlbox-results" \
./scripts/package_release.sh dist
```

The default artifact is named `interspec-typed-allocator-0.1.0.tar.gz` and is accompanied by a SHA256 checksum. In addition to the installed runtime and earlier P6/P7 documentation, the archive contains `P8_EVALUATION.md`, a mechanically rendered `P8_RESULTS.md`, deterministic/security/automation records, trusted-metadata runtime measurements, paired real-boundary summaries, paired rsync summaries, environment metadata, release notes, reproducibility instructions, and pinned manifests.

The package script verifies the required P8 files before creating the archive and rejects a deterministic report that is not complete.

No license is inferred or added by the packaging script. Publication under a particular software license should be an explicit project decision rather than an artifact generation side effect.

## 10. Publish a tagged GitHub research preview

`.github/workflows/release.yml` regenerates P8 deterministic and RLBox evidence before building the same validated archive when a version tag is pushed. The tag must match the CMake project version exactly and must point at the current `main` head.

For the current preview, the expected tag is:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow attaches both the archive and SHA256 checksum to a GitHub release using `RELEASE_NOTES.md`. Creating the tag is intentionally a separate explicit publication action. Ordinary branch or pull-request CI produces preview artifacts but does not publish a GitHub release.
