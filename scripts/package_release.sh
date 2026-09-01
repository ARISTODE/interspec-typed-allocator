#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/dist"}
version=${INTERSPEC_RELEASE_VERSION:-0.1.0}
build=${INTERSPEC_RELEASE_BUILD_DIR:-"$root/build-release"}
stage="$build/stage"
package="$out/interspec-typed-allocator-$version"
archive="$out/interspec-typed-allocator-$version.tar.gz"
p8_eval=${INTERSPEC_P8_EVAL_DIR:-}
p8_rlbox=${INTERSPEC_P8_RLBOX_DIR:-}

if [[ -z "$p8_eval" || -z "$p8_rlbox" ]]; then
  cat >&2 <<'EOF'
complete P8 evidence is required to build the research preview archive.
Generate or download both result directories, then set:
  INTERSPEC_P8_EVAL_DIR=/path/to/p8-results
  INTERSPEC_P8_RLBOX_DIR=/path/to/p8-rlbox-results
EOF
  exit 1
fi

for path in \
  "$p8_eval/p8-deterministic.json" \
  "$p8_eval/p8-automation.csv" \
  "$p8_eval/p7c-generalization.json" \
  "$p8_eval/p6/security.csv" \
  "$p8_eval/p6/runtime.csv" \
  "$p8_eval/environment.txt" \
  "$p8_rlbox/boundary-performance.csv" \
  "$p8_rlbox/boundary-performance-summary.csv" \
  "$p8_rlbox/rsync-performance.csv" \
  "$p8_rlbox/rsync-performance-summary.csv" \
  "$p8_rlbox/environment.txt"; do
  if [[ ! -s "$path" ]]; then
    echo "missing required P8 release evidence: $path" >&2
    exit 1
  fi
done

python3 - "$p8_eval/p8-deterministic.json" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1]))
if not report.get("deterministic_complete", False):
    raise SystemExit("P8 deterministic report is not complete")
PY

rm -rf "$build" "$package"
mkdir -p "$out"
cmake -S "$root" -B "$build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$build" --parallel
ctest --test-dir "$build" --output-on-failure
cmake --install "$build" --prefix "$stage"
cmake -S "$root/examples/consumer" -B "$build/consumer" -DCMAKE_PREFIX_PATH="$stage"
cmake --build "$build/consumer" --parallel
"$build/consumer/interspec_runtime_consumer"
mkdir -p "$package"
cp -a "$stage"/. "$package"/
mkdir -p "$package/share/interspec-typed-allocator"
for doc in README.md P6_EVALUATION.md P6_RESULTS.md P7A_PROVENANCE.md \
           P7B_NATIVE_INTEGRATION.md P7C_GENERALIZATION.md P7C_RESULTS.md \
           P8_EVALUATION.md P9A_EVALUATION.md P9B_EVALUATION.md \
           RELEASE_NOTES.md REPRODUCIBILITY.md; do
  cp "$root/$doc" "$package/share/interspec-typed-allocator/"
done
cp "$root/backends/rlbox_nacl/manifest.json" \
  "$package/share/interspec-typed-allocator/rlbox_nacl_manifest.json"
cp "$root/backends/rlbox_wasm2c/manifest.json" \
  "$package/share/interspec-typed-allocator/rlbox_wasm2c_manifest.json"
cp "$root/integration/p7c_manifest.json" \
  "$package/share/interspec-typed-allocator/p7c_manifest.json"

p8_share="$package/share/interspec-typed-allocator/p8"
mkdir -p "$p8_share/p6"
cp "$p8_eval/p8-deterministic.json" "$p8_share/"
cp "$p8_eval/p8-automation.csv" "$p8_share/"
cp "$p8_eval/p7c-generalization.json" "$p8_share/"
cp "$p8_eval/environment.txt" "$p8_share/evaluation-environment.txt"
cp "$p8_eval/p6/security.csv" "$p8_share/p6/"
cp "$p8_eval/p6/runtime.csv" "$p8_share/p6/"
cp "$p8_rlbox/boundary-performance.csv" "$p8_share/"
cp "$p8_rlbox/boundary-performance-summary.csv" "$p8_share/"
cp "$p8_rlbox/rsync-performance.csv" "$p8_share/"
cp "$p8_rlbox/rsync-performance-summary.csv" "$p8_share/"
cp "$p8_rlbox/environment.txt" "$p8_share/rlbox-environment.txt"

reference_commit=$(git -C "$root" rev-parse HEAD 2>/dev/null || echo unknown)
python3 "$root/tools/render_p8_results.py" \
  --deterministic "$p8_eval/p8-deterministic.json" \
  --automation "$p8_eval/p8-automation.csv" \
  --runtime "$p8_eval/p6/runtime.csv" \
  --boundary-summary "$p8_rlbox/boundary-performance-summary.csv" \
  --application-summary "$p8_rlbox/rsync-performance-summary.csv" \
  --commit "$reference_commit" \
  --environment "$p8_rlbox/environment.txt" \
  --output "$package/share/interspec-typed-allocator/P8_RESULTS.md"
cp "$package/share/interspec-typed-allocator/P8_RESULTS.md" "$p8_share/P8_RESULTS.md"

for path in \
  "$package/share/interspec-typed-allocator/P8_EVALUATION.md" \
  "$package/share/interspec-typed-allocator/P9A_EVALUATION.md" \
  "$package/share/interspec-typed-allocator/P9B_EVALUATION.md" \
  "$package/share/interspec-typed-allocator/rlbox_nacl_manifest.json" \
  "$package/share/interspec-typed-allocator/rlbox_wasm2c_manifest.json" \
  "$package/share/interspec-typed-allocator/P8_RESULTS.md" \
  "$p8_share/p8-deterministic.json" \
  "$p8_share/p8-automation.csv" \
  "$p8_share/p6/runtime.csv" \
  "$p8_share/boundary-performance-summary.csv" \
  "$p8_share/rsync-performance-summary.csv"; do
  test -s "$path"
done

rm -f "$archive" "$archive.sha256"
tar -C "$out" -czf "$archive" "interspec-typed-allocator-$version"
sha256sum "$archive" > "$archive.sha256"
echo "release archive: $archive"
echo "checksum: $archive.sha256"
