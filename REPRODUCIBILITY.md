# Reproducibility

This repository pins the external source revisions used by the RLBox + NaCl proof and provides one command for each evaluation layer.

## 1. Required environment

The lightweight runtime, policy generation, and P6 evaluation use a C++17 compiler, CMake, Python 3, and pthread support.

The full RLBox + NaCl integration is tested in the repository CI with Ubuntu 20.04 and installs the build dependencies listed in `.github/workflows/ci.yml` before invoking `scripts/run_rlbox_nacl_poc.sh`.

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

The RLBox and NaCl revisions are also recorded in `backends/rlbox_nacl/manifest.json`. The integration script refuses to treat arbitrary upstream revisions as equivalent to the packaged backend.

## 3. Core correctness

```bash
cmake -S . -B build
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

This runs the mechanism PoC, runtime hardening tests, policy generation tests, and the P6 security evaluation.

## 4. Source policy inference

The CodeQL CI job regenerates both checked in policy snapshots from source and requires exact equality.

When CodeQL is available on `PATH`, run:

```bash
chmod +x scripts/run_policy_inference.sh
./scripts/run_policy_inference.sh

chmod +x scripts/run_rsync_popt_policy_inference.sh
./scripts/run_rsync_popt_policy_inference.sh
```

A mismatch is a failure rather than an automatic policy update. This makes policy drift visible for review.

## 5. P6 security and runtime evaluation

```bash
chmod +x scripts/run_p6_evaluation.sh
./scripts/run_p6_evaluation.sh
```

The result directory contains the exact security matrix, runtime measurements, test output, commit identifier, compiler version, CMake version, kernel description, and configured benchmark iteration count.

For more stable performance comparison, use a dedicated machine and raise the repetition count, for example:

```bash
INTERSPEC_BENCH_ITERATIONS=2000000 ./scripts/run_p6_evaluation.sh
```

Do not compare absolute nanosecond values from unrelated machines as if they were controlled experiments.

## 6. Full RLBox + NaCl application path

```bash
chmod +x scripts/run_rlbox_nacl_poc.sh
./scripts/run_rlbox_nacl_poc.sh
```

The script clones the pinned RLBox, NaCl, and rsync revisions, applies the packaged backend, regenerates typed allocation policy artifacts, builds the sandboxed parser and trusted integration, executes the synthetic and real boundary tests, and exercises the complete rsync P4c path.

Network access is required because the external repositories are cloned during the run.

## 7. Install and external consumer test

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

## 8. Build the research preview archive

```bash
chmod +x scripts/package_release.sh
./scripts/package_release.sh
```

The default artifact is named `interspec-typed-allocator-0.1.0.tar.gz` and is accompanied by a SHA256 checksum file. The archive includes the installed runtime package plus the README, P6 evaluation methodology, representative results, release notes, reproducibility instructions, and pinned RLBox + NaCl manifest.

No license is inferred or added by the packaging script. Publication under a particular software license should be an explicit project decision rather than an artifact generation side effect.

## 9. Publish a tagged GitHub research preview

`.github/workflows/release.yml` publishes the same validated archive when a version tag is pushed. The tag must match the CMake project version exactly.

For the current preview, the expected tag is:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow rebuilds the package, reruns the core test suite and external consumer smoke test through `scripts/package_release.sh`, verifies the tag against the project version, and attaches both the archive and SHA256 checksum to a GitHub release using `RELEASE_NOTES.md`.

Creating the tag is intentionally a separate explicit publication action. Ordinary branch or pull request CI produces preview artifacts but does not publish a GitHub release.
