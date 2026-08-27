#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/p6-results"}
build=${INTERSPEC_P6_BUILD_DIR:-"$root/build-p6"}

rm -rf "$build" "$out"
mkdir -p "$out"

cmake -S "$root" -B "$build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$build" --parallel
ctest --test-dir "$build" --output-on-failure | tee "$out/ctest.txt"

"$build/p6_security_eval" | tee "$out/security.csv"
"$build/p6_runtime_bench" | tee "$out/runtime.csv"

{
  echo "commit=$(git -C "$root" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "compiler=$(${CXX:-c++} --version | head -n 1)"
  echo "cmake=$(cmake --version | head -n 1)"
  echo "kernel=$(uname -srmo)"
  echo "iterations=${INTERSPEC_BENCH_ITERATIONS:-200000}"
} > "$out/environment.txt"

echo "P6 evaluation results written to $out"
