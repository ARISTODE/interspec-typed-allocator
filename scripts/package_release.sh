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

cmake -S "$root/examples/consumer" -B "$build/consumer" \
  -DCMAKE_PREFIX_PATH="$stage"
cmake --build "$build/consumer" --parallel
"$build/consumer/interspec_runtime_consumer"

mkdir -p "$package"
cp -a "$stage"/. "$package"/
mkdir -p "$package/share/interspec-typed-allocator"
cp "$root/README.md" "$package/share/interspec-typed-allocator/"
cp "$root/P6_EVALUATION.md" "$package/share/interspec-typed-allocator/"
cp "$root/P6_RESULTS.md" "$package/share/interspec-typed-allocator/"
cp "$root/P7A_PROVENANCE.md" "$package/share/interspec-typed-allocator/"
cp "$root/P7B_NATIVE_INTEGRATION.md" "$package/share/interspec-typed-allocator/"
cp "$root/RELEASE_NOTES.md" "$package/share/interspec-typed-allocator/"
cp "$root/REPRODUCIBILITY.md" "$package/share/interspec-typed-allocator/"
cp "$root/backends/rlbox_nacl/manifest.json" \
  "$package/share/interspec-typed-allocator/rlbox_nacl_manifest.json"

rm -f "$archive" "$archive.sha256"
tar -C "$out" -czf "$archive" "interspec-typed-allocator-$version"
sha256sum "$archive" > "$archive.sha256"

echo "release archive: $archive"
echo "checksum: $archive.sha256"
