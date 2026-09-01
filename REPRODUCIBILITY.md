# Reproducibility

This repository pins the external source revisions used by the RLBox + NaCl and RLBox + wasm2c proofs and provides a reproducible path from policy inference through P8 and P9 evidence and release packaging.

## 1. Required environment

The lightweight runtime, policy generation, P6 evaluation, deterministic P8 report, and P9c paper coverage reconciliation use a C++17 compiler, CMake, Python 3, and pthread support.

The full RLBox + NaCl integration is tested in repository CI with Ubuntu 20.04. The P9b RLBox + wasm2c integration is tested on the repository's current Ubuntu GitHub hosted runner. Each job installs the build dependencies listed in `.github/workflows/ci.yml` before invoking its integration driver.

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

RLBox API used by P9b:

```text
repository: https://github.com/PLSysSec/rlbox.git
commit: b0157dc84f86ffbe4549e32ed5cbdfad79c17f43
```

WABT / wasm2c used by P9b:

```text
repository: https://github.com/WebAssembly/wabt.git
commit: 974221b1ef82f6393d004e5da6116f2ad3e44005
```

P9b uses wasi sdk 21.0 through the pinned upstream wasm2c build path.

Rsync source used by the real popt boundary:

```text
repository: https://github.com/RsyncProject/rsync.git
commit: 7c20b077c980036a19587701cec320cc88e42a4a
```

Final InterSpec paper artifact used by P9c:

```text
repository: ARISTODE/interspec-artifact
artifact commit: 2b2d2fd4de69ee44a4363e69f8cfb82ceed132db
paper source commit: c692d9581e17689ca1dc20545c48a355c6a86ff6
processed coverage table: data/processed/paper/integrity_coverage.csv
processed coverage blob: 5c5f0e9b4b4a5b548504653680d0cf158d2db613
```

The NaCl revisions are recorded in `backends/rlbox_nacl/manifest.json`. The wasm2c revisions are recorded in `backends/rlbox_wasm2c/manifest.json`. Real boundary source revisions are recorded in the integration manifests consumed by the P7c and P8 report. P9c records the final paper coverage source in `evaluation/p9c/paper_sp3_manifest.json`. The integration and evaluation scripts refuse to treat arbitrary upstream revisions or changed paper denominators as equivalent to the evaluated configuration.

## 3. Core correctness

```bash
cmake -S . -B build
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

This runs the mechanism PoC, runtime hardening tests, policy generation tests, P6 security evaluation, P7c report checks, P8 report and rendering tests, P9a baseline aggregation tests, P9b wasm direct provenance and code generation tests, and the P9c paper coverage reconciliation test.

## 4. Source policy inference

The CodeQL CI job regenerates checked in policy snapshots from source and requires exact equality. It covers the runtime policy, rsync/popt, memcached/bipbuffer, nginx/libpcre, and yaml/libyaml integration policies.

When CodeQL is available on `PATH`, the same repository scripts can be run directly:

```bash
./scripts/run_policy_inference.sh
./scripts/run_rsync_popt_policy_inference.sh
./scripts/run_memcached_bipbuffer_policy_inference.sh
./scripts/run_nginx_libpcre_policy_inference.sh
./scripts/run_yaml_libyaml_policy_inference.sh
```

A mismatch is a failure rather than an automatic policy update. This makes policy drift visible for review.

## 5. P6 security and trusted metadata runtime evaluation

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

This reuses the P6 security and runtime path, requires the P7c generalization report to be complete, and produces the machine readable P8 completion and automation records. The key outputs are `p8-deterministic.json`, `p8-automation.csv`, `p7c-generalization.json`, and the inherited P6 security and runtime CSV files.

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

The P8 driver clones the pinned RLBox, NaCl, rsync, and boundary source revisions as required, applies the packaged backend, regenerates typed allocation policy artifacts, builds the sandboxed integrations, executes the synthetic and real boundary regressions, and produces paired boundary and application timing evidence.

The P8 paired baseline is `tracked_no_check`: sandboxing, typed allocation and provenance, policy registration, and marshalling remain enabled, while only the final T side Extended SP3 pointer acceptance check is bypassed. P9a additionally produces a three way rsync/popt comparison with `rlbox_only`, `tracked_no_check`, and `extended_sp3` so tracking and provenance cost can be separated from final validation cost on the NaCl prototype path.

Network access is required because the external repositories are cloned during the run. Hosted CI timings are reproducible reference measurements. Final publication timing numbers should be regenerated on controlled hardware with the same output format.

## 8. P9b RLBox wasm2c integration

P9b ports the allocation provenance and Extended SP3 trusted use checks to the wasm2c backend used by the InterSpec paper. The full end to end command is:

```bash
chmod +x scripts/run_rlbox_wasm2c_poc.sh
./scripts/run_rlbox_wasm2c_poc.sh
```

The driver performs the complete experiment from a fresh directory. It clones the pinned `rlbox_wasm2c_sandbox` and rsync revisions, applies `backends/rlbox_wasm2c/apply_backend.py`, pins the RLBox and WABT revisions from the backend manifest, regenerates the rsync/popt policy with `tools/generate_wasm_boundary_policy.py`, compiles the real bundled popt implementation into Wasm, and builds the wasm2c runtime.

For allocation provenance, each precise source site and explicit helper site is rewritten to a distinct direct Wasm import. The Wasm call supplies only the allocation size. Its trusted host wrapper embeds the corresponding SiteId and dispatches to T's SiteId to TypeId policy, so U does not provide either authority value as ordinary data.

The driver then executes `p9b_wasm_smoke`, which verifies valid tracked use, spatial overflow rejection, ordinary same domain untracked pointer rejection, wrong type rejection, and stale pointer rejection after logical free. Finally, it mechanically transforms the existing rsync/popt trusted bridge to wasm2c, builds the complete trusted rsync executable, and runs both the option parsing and local dry run workloads with the real bundled popt executing inside RLBox wasm2c.

Successful output includes both of these markers:

```text
InterSpec P9b: wasm2c security smoke passed
InterSpec P9b: complete rsync executable ran with popt inside RLBox wasm2c
```

The P9b CI job is a required predecessor of `release-smoke`, so a branch cannot pass the full CI graph while the wasm2c integration is broken. P9b is a backend and security integration result, not a publication quality performance result.

## 9. P9c final paper SP3 coverage reconciliation

P9c reproduces the final InterSpec paper's SP3 denominator and audits whether the preserved artifact supports exact field level Extended SP3 applicability claims.

```bash
chmod +x scripts/run_p9c_evaluation.sh
./scripts/run_p9c_evaluation.sh p9c-results
```

A successful run produces:

```text
p9c-report.json
p9c-cases.csv
P9C_RESULTS.md
paper_sp3_manifest.json
source_reconstruction_audit.json
interspec_paper_integrity_coverage.csv
environment.txt
README.txt
```

The evaluator requires the final table to contain exactly 32 SP3 pointer fields across the same 10 boundaries. `p9c-cases.csv` contains exactly 32 stable count unit identifiers, one for each field counted by the paper. These identifiers do not invent original source field names.

The source reconstruction audit records why the final paper artifact does not support a complete one row per paper field identity map. The final processed table is aggregate only, while preserved raw reports differ from that table in granularity, cardinality, report version, or boundary coverage. For example, the final table counts three magick/libpng SP3 fields while the packaged raw case file has two rows. The preserved nginx/OpenSSL provenance evidence also uses a raw analysis granularity that is different from the final paper counts.

The expected P9c result therefore has:

```text
paper_source_integrity=true
classification_explicit=true
source_reconstruction_audit_complete=true
source_fidelity_limit_acknowledged=true
p9c_evaluation_complete=true
capability_resolution_complete=false
source_fidelity_complete=false
paper.sp3_case_count=32
coverage_claim.exact_case_level_percentage_supported=false
```

The exact eligible and exact demonstrated lower bounds are both currently 0 of 32. These are provenance lower bounds, not estimates that Extended SP3 applies to zero cases. The repository's real boundary integrations remain valid mechanism evidence, but P9c refuses to convert those demonstrations into a guessed exact percentage of the original 32 fields.

The P9c CI job runs with `--require-source-integrity` and `--require-complete`. This permits completion through an audited source fidelity limitation while still failing if the paper denominator changes, a case unit disappears, or the audit evidence becomes inconsistent.

## 10. Install and external consumer test

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

## 11. Build the complete research preview archive

The release archive intentionally requires P8 deterministic evidence, P8 RLBox evidence, and the complete P9c reconciliation evidence. A green packaging job therefore cannot silently publish an artifact that omits the final paper coverage audit. P9a hosted timing artifacts remain CI evidence rather than a release prerequisite, while P9b is enforced by the independent wasm2c CI predecessor.

```bash
./scripts/run_p8_evaluation.sh p8-results
./scripts/run_p8_rlbox_evaluation.sh p8-rlbox-results
./scripts/run_p9c_evaluation.sh p9c-results

INTERSPEC_P8_EVAL_DIR="$PWD/p8-results" \
INTERSPEC_P8_RLBOX_DIR="$PWD/p8-rlbox-results" \
INTERSPEC_P9C_EVAL_DIR="$PWD/p9c-results" \
./scripts/package_release.sh dist
```

The default artifact is named `interspec-typed-allocator-0.1.0.tar.gz` and is accompanied by a SHA256 checksum. In addition to the installed runtime and earlier P6 and P7 documentation, the archive contains `P8_EVALUATION.md`, `P9A_EVALUATION.md`, `P9B_EVALUATION.md`, `P9C_EVALUATION.md`, mechanically rendered `P8_RESULTS.md` and `P9C_RESULTS.md`, deterministic and security and automation records, trusted metadata runtime measurements, paired real boundary summaries, paired rsync summaries, the complete P9c case and reconstruction audit evidence, environment metadata, release notes, reproducibility instructions, and the pinned NaCl and wasm2c manifests.

The package script verifies the required P8 and P9c files before creating the archive. It rejects an incomplete P8 deterministic report, a P9c report whose `p9c_evaluation_complete` flag is false, or a P9c paper denominator other than 32.

No license is inferred or added by the packaging script. Publication under a particular software license should be an explicit project decision rather than an artifact generation side effect.

## 12. Publish a tagged GitHub research preview

`.github/workflows/release.yml` regenerates P8 deterministic and NaCl evidence, regenerates P9c paper coverage reconciliation evidence, and independently reruns the complete P9b wasm2c integration before building the validated archive when a version tag is pushed. The release job cannot start unless all three evidence gates pass. The tag must match the CMake project version exactly and must point at the current `main` head.

For the current preview, the expected tag is:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow attaches both the archive and SHA256 checksum to a GitHub release using `RELEASE_NOTES.md`. Creating the tag is intentionally a separate explicit publication action. Ordinary branch or pull request CI produces preview artifacts but does not publish a GitHub release.
