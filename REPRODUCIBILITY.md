# Reproducibility

This repository pins the external source revisions used by the RLBox + NaCl and RLBox + wasm2c proofs and provides a reproducible path from policy inference through P8/P9/P10/P11 backend evidence and release packaging.

## 1. Required environment

The lightweight runtime, policy generation, P6 evaluation, and deterministic P8 report use a C++17 compiler, CMake, Python 3, and pthread support.

The full RLBox + NaCl integration is tested in repository CI with Ubuntu 20.04. The P9b, P10, and P11 RLBox + wasm2c paths are tested on the repository's current Ubuntu GitHub-hosted runner. Each job installs the build dependencies listed in the workflow before invoking its integration driver.

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

RLBox wasm2c sandbox:

```text
repository: https://github.com/PLSysSec/rlbox_wasm2c_sandbox.git
commit: c4f18c48cea47421617f72ba5edc95c68aa85671
```

RLBox API used by P9b/P10/P11:

```text
repository: https://github.com/PLSysSec/rlbox.git
commit: b0157dc84f86ffbe4549e32ed5cbdfad79c17f43
```

WABT / wasm2c used by P9b/P10/P11:

```text
repository: https://github.com/WebAssembly/wabt.git
commit: 974221b1ef82f6393d004e5da6116f2ad3e44005
```

P9b/P10/P11 use wasi-sdk 21.0 through the pinned upstream wasm2c build path.

Real-boundary source revisions:

```text
rsync/popt: 7c20b077c980036a19587701cec320cc88e42a4a
memcached/bipbuffer: 2d51e364799bc9698bd4b11728ea978cea12da6e
nginx/libpcre pattern: e67dabe61b327bd2d888954b0e74a7c9cfd0a195
yaml/libyaml: 90a56d4500aa1a1798514c5cb55c3ad4cb095f94
```

The NaCl revisions are recorded in `backends/rlbox_nacl/manifest.json`. The wasm2c revisions are recorded in `backends/rlbox_wasm2c/manifest.json`. Real-boundary source revisions are recorded in `integration/p7c_manifest.json`. The integration scripts explicitly check out these revisions rather than treating arbitrary upstream revisions as equivalent to the evaluated configuration.

## 3. Core correctness

```bash
cmake -S . -B build
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

This runs the mechanism PoC, runtime hardening tests, policy generation tests, P6 security evaluation, P7c report checks, P8 report/rendering tests, P9a baseline aggregation tests, P9b wasm-direct provenance/code-generation tests, and the P11 wasm2c RLBox-only bridge transformation test.

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

## 7. Full RLBox + NaCl integration and P8/P9a measurements

```bash
chmod +x scripts/run_rlbox_nacl_poc.sh \
  scripts/run_yaml_libyaml_rlbox_extension.sh \
  scripts/write_p8_rlbox_environment.sh \
  scripts/run_p8_rlbox_evaluation.sh \
  scripts/collect_p9a_rlbox_results.sh

INTERSPEC_P8_BOUNDARY_ITERATIONS=20000 \
INTERSPEC_P8_APP_REPETITIONS=9 \
INTERSPEC_P9A_APP_REPETITIONS=9 \
./scripts/run_p8_rlbox_evaluation.sh p8-rlbox-results

./scripts/collect_p9a_rlbox_results.sh p9a-rlbox-results
```

The P8 driver clones the pinned RLBox, NaCl, rsync, and boundary source revisions as required, applies the packaged backend, regenerates typed allocation policy artifacts, builds the sandboxed integrations, executes the synthetic and real-boundary regressions, and produces paired boundary/application timing evidence.

The P8 paired baseline is `tracked_no_check`: sandboxing, typed allocation/provenance, policy registration, and marshalling remain enabled, while only the final T-side Extended-SP3 pointer acceptance check is bypassed. P9a additionally produces a three-way rsync/popt comparison with `rlbox_only`, `tracked_no_check`, and `extended_sp3` so tracking/provenance cost can be separated from final validation cost on the NaCl prototype path.

Network access is required because the external repositories are cloned during the run. Hosted CI timings are reproducible reference measurements. Final publication timing numbers should be regenerated on controlled hardware with the same output format.

## 8. P9b RLBox wasm2c integration

P9b ports the allocation provenance and Extended-SP3 trusted-use checks to the wasm2c backend used by the InterSpec paper. The full end-to-end command is:

```bash
chmod +x scripts/run_rlbox_wasm2c_poc.sh
./scripts/run_rlbox_wasm2c_poc.sh
```

The driver performs the complete experiment from a fresh directory. It clones the pinned `rlbox_wasm2c_sandbox` and rsync revisions, applies `backends/rlbox_wasm2c/apply_backend.py`, pins the RLBox and WABT revisions from the backend manifest, regenerates the rsync/popt policy with `tools/generate_wasm_boundary_policy.py`, compiles the real bundled popt implementation into Wasm, and builds the wasm2c runtime.

For allocation provenance, each precise source site and explicit helper site is rewritten to a distinct direct Wasm import. The Wasm call supplies only the allocation size. Its trusted host wrapper embeds the corresponding SiteId and dispatches to T's SiteId-to-TypeId policy, so U does not provide either authority value as ordinary data.

The driver then executes `p9b_wasm_smoke`, which verifies valid tracked use, spatial overflow rejection, ordinary same-domain untracked-pointer rejection, wrong-type rejection, and stale-pointer rejection after logical free. Finally, it mechanically transforms the existing rsync/popt trusted bridge to wasm2c, builds the complete trusted rsync executable, and runs both the option-parsing and local dry-run workloads with the real bundled popt executing inside RLBox wasm2c.

Successful output includes both of these markers:

```text
InterSpec P9b: wasm2c security smoke passed
InterSpec P9b: complete rsync executable ran with popt inside RLBox wasm2c
```

P9b is a backend/security integration result, not a publication-quality performance result.

## 9. P10 P7c boundaries on RLBox wasm2c

P10 reuses the P9b wasm-direct provenance and runtime path for the three P7c generalization boundaries. Run:

```bash
chmod +x scripts/run_p7c_wasm2c.sh
./scripts/run_p7c_wasm2c.sh
```

The driver starts from a fresh directory, clones the pinned RLBox wasm2c backend and all three pinned upstream libraries, regenerates each boundary's wasm-direct allocation policy, and builds one combined Wasm module.

The boundary-specific policy composition remains faithful to P7c. `memcached/bipbuffer` uses one precise source-derived allocation site. `nginx/libpcre` uses an explicit helper site for the compiled-regex allocation through the PCRE allocator abstraction. `yaml/libyaml` uses an explicit helper site for scalar-value allocation through `YAML_MALLOC`.

`integration/p7c_wasm_smoke.cpp` then executes all three valid trusted-use paths and verifies rejection of tracked wrong-type memory, ordinary same-domain untracked memory, and corrupted runtime extents.

Successful output ends with:

```text
InterSpec P10: memcached/bipbuffer passed in RLBox wasm2c
InterSpec P10: nginx/libpcre passed in RLBox wasm2c
InterSpec P10: yaml/libyaml passed in RLBox wasm2c
InterSpec P10: all P7c generalization boundaries passed on wasm2c
```

The dedicated `.github/workflows/p10-wasm2c-p7c.yml` workflow runs this command for every push and pull request. The tagged release workflow independently reruns P10 before publication.

## 10. P11 final wasm2c performance evaluation

P11 moves the P9a three-way cost decomposition to the final wasm2c path. Run the short reference form with:

```bash
chmod +x scripts/run_p11_wasm2c_performance.sh
./scripts/run_p11_wasm2c_performance.sh p11-wasm2c-results
```

The driver reuses the complete P9b preparation path, then builds immutable `rlbox_only`, `tracked_no_check`, and `extended_sp3` rsync binaries. The RLBox-only module restores pinned uninstrumented bundled popt, disables typed allocator interposition, uses ordinary sandbox input allocation, does not reserve the typed region or initialize `PolicyRuntime`, and bypasses the final Extended-SP3 check for known-valid benchmark data.

Each repetition contains all three modes and rotates through all six execution orders. The artifact contains raw complete-process timings, a mechanical summary, a rendered table, and host metadata.

For publication-quality data, run the same driver on a controlled host, for example:

```bash
INTERSPEC_P11_REPETITIONS=31 \
INTERSPEC_P11_WARMUPS=3 \
INTERSPEC_P11_CPU=2 \
./scripts/run_p11_wasm2c_performance.sh p11-wasm2c-results
```

The script records the observed CPU, kernel, frequency governor, turbo/boost state when exposed, affinity request, repetition count, and source revisions. It does not change power-management settings. GitHub-hosted P11 results are reference evidence only and must not be presented as the final controlled-hardware numbers.

## 11. Install and external consumer test

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

## 12. Build the complete research preview archive

The release archive intentionally requires both P8 evidence directories so a green packaging job cannot silently publish a pre-P8 artifact. The package records the P9a/P9b/P10/P11 evaluation documentation and both backend manifests. P11 timing artifacts remain separate CI or controlled-host evidence rather than a release prerequisite because hosted timing is not the publication result.

```bash
./scripts/run_p8_evaluation.sh p8-results
./scripts/run_p8_rlbox_evaluation.sh p8-rlbox-results

INTERSPEC_P8_EVAL_DIR="$PWD/p8-results" \
INTERSPEC_P8_RLBOX_DIR="$PWD/p8-rlbox-results" \
./scripts/package_release.sh dist
```

The default artifact is named `interspec-typed-allocator-0.1.0.tar.gz` and is accompanied by a SHA256 checksum. In addition to the installed runtime and earlier P6/P7 documentation, the archive contains `P8_EVALUATION.md`, `P9A_EVALUATION.md`, `P9B_EVALUATION.md`, `P10_WASM2C_P7C.md`, `P11_EVALUATION.md`, a mechanically rendered `P8_RESULTS.md`, deterministic/security/automation records, trusted-metadata runtime measurements, paired real-boundary summaries, paired rsync summaries, environment metadata, release notes, reproducibility instructions, and the pinned NaCl and wasm2c manifests.

The package script verifies the required P8 files and P10/P11 documentation before creating the archive and rejects a deterministic report that is not complete.

No license is inferred or added by the packaging script. Publication under a particular software license should be an explicit project decision rather than an artifact generation side effect.

## 13. Publish a tagged GitHub research preview

`.github/workflows/release.yml` regenerates P8 deterministic and NaCl evidence and independently reruns the complete P9b and P10 wasm2c integrations before building the validated archive when a version tag is pushed. P11 methodology is packaged, but the release workflow intentionally does not manufacture a hosted performance number and call it controlled-hardware evidence. The tag must match the CMake project version exactly and must point at the current `main` head.

For the current preview, the expected tag is:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow attaches both the archive and SHA256 checksum to a GitHub release using `RELEASE_NOTES.md`. Creating the tag is intentionally a separate explicit publication action. Ordinary branch or pull-request CI produces preview artifacts but does not publish a GitHub release.
