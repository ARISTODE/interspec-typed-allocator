#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/dist"}
version=${INTERSPEC_RELEASE_VERSION:-0.1.0}
build=${INTERSPEC_RELEASE_BUILD_DIR:-"$root/build-release"}
stage="$build/stage"
package="$out/interspec-typed-allocator-$version"
archive="$out/interspec-typed-allocator-$version.tar.gz"

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
           P8_EVALUATION.md P8_RESULTS.md RELEASE_NOTES.md REPRODUCIBILITY.md; do
  cp "$root/$doc" "$package/share/interspec-typed-allocator/"
done
cp "$root/backends/rlbox_nacl/manifest.json" \
  "$package/share/interspec-typed-allocator/rlbox_nacl_manifest.json"
cp "$root/integration/p7c_manifest.json" \
  "$package/share/interspec-typed-allocator/p7c_manifest.json"
cp "$root/evaluation/p8_manifest.json" \
  "$package/share/interspec-typed-allocator/p8_manifest.json"
rm -f "$archive" "$archive.sha256"
tar -C "$out" -czf "$archive" "interspec-typed-allocator-$version"
sha256sum "$archive" > "$archive.sha256"
echo "release archive: $archive"
echo "checksum: $archive.sha256"
