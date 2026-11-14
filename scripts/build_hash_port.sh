#!/usr/bin/env bash
# Build step of scripts/run_hash_port.sh (tracker item I9). A separate script,
# run with errexit, so that any failing command fails the build.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${1:?usage: build_hash_port.sh WORK_DIR}
mkdir -p "$work"
source "$root/scripts/port_common.sh"
port_deps
port_source memcached
memcached="$work/src-memcached" dir="$root/integration/memcached_hash"

# The artifact's hash_untrusted.c includes ../../benchmarks/memcached/xxhash.h
# relative to its own directory. Recreate that layout with the unchanged file
# and xxhash.h from memcached at the pinned revision.
layout="$work/layout/samples"
mkdir -p "$layout/memcached_hash_bridge_wasm/untrusted" "$layout/benchmarks/memcached"
cp "$dir/samples/memcached_hash_bridge_wasm/untrusted/hash_untrusted.c" \
   "$layout/memcached_hash_bridge_wasm/untrusted/"
cp "$memcached/xxhash.h" "$layout/benchmarks/memcached/"
shim="$layout/memcached_hash_bridge_wasm/untrusted/hash_untrusted.c"

# No registry at this boundary (U returns a number), so one module serves both
# isolated variants; the test build adds the hook.
port_module ordinary - -- "$dir/hash_u.c" "$shim"
port_module fault - -- -DINTERSPEC_FAULT_TESTS=1 "$dir/hash_u.c" "$shim"
if grep -q 'interspec_hash_poc' "$work/ordinary/glue_lib_wasm2c.h"; then
  echo 'Release module unexpectedly contains test hooks' >&2; exit 1
fi

mkdir -p "$work/bin" "$work/native"
cc -O3 -c "$shim" -o "$work/native/hash_untrusted.o"
g++ -std=c++17 -O2 -I"$dir" "$dir/hash_native_bench.cpp" "$work/native/hash_untrusted.o" \
  -o "$work/bin/hash-native"
port_host "$work/bin/hash-rlbox-only" ordinary 0 0 -- -I"$dir" "$dir/hash_app_bench.cpp"
port_host "$work/bin/hash-interspec" ordinary 0 1 -- -I"$dir" "$dir/hash_app_bench.cpp"
port_host "$work/bin/hash-interspec-fault" fault 0 1 -- -I"$dir" \
  -DINTERSPEC_FAULT_TESTS=1 "$dir/hash_app_bench.cpp"

# The hash table in U (JH decision of 2026-11-14): memcached's assoc logic on
# U's copies of the items (assoc_u.c), in one module with the hash function.
port_module assoc - -- -I"$dir" "$dir/hash_u.c" "$dir/assoc_u.c" "$shim"
port_module assoc-fault - -- -I"$dir" -DINTERSPEC_FAULT_TESTS=1 \
  "$dir/hash_u.c" "$dir/assoc_u.c" "$shim"
if grep -q 'interspec_assoc_fault\|interspec_assoc_poc' "$work/assoc/glue_lib_wasm2c.h"; then
  echo 'Release module unexpectedly contains test hooks' >&2; exit 1
fi
cc -O3 -I"$dir" -c "$dir/assoc_u.c" -o "$work/native/assoc_u.o"
g++ -std=c++17 -O2 -I"$dir" "$dir/assoc_native_bench.cpp" "$work/native/assoc_u.o" \
  "$work/native/hash_untrusted.o" -o "$work/bin/assoc-native"
port_host "$work/bin/assoc-rlbox-only" assoc 0 0 -- -I"$dir" "$dir/assoc_app_bench.cpp"
port_host "$work/bin/assoc-interspec" assoc 0 1 -- -I"$dir" "$dir/assoc_app_bench.cpp"
# For P7: T registers its items and never checks a handle against the registry.
port_host "$work/bin/assoc-tracked-no-check" assoc 0 0 -- -I"$dir" -DINTERSPEC_T_TRACKING=1 \
  "$dir/assoc_app_bench.cpp"
port_host "$work/bin/assoc-interspec-fault" assoc-fault 0 1 -- -I"$dir" \
  -DINTERSPEC_FAULT_TESTS=1 "$dir/assoc_app_bench.cpp"
port_host "$work/bin/assoc-rlbox-only-fault" assoc-fault 0 0 -- -I"$dir" \
  -DINTERSPEC_FAULT_TESTS=1 "$dir/assoc_app_bench.cpp"
(cd "$work/bin" && sha256sum hash-* assoc-*) > "$work/binaries.sha256"
echo "memcached $(git -C "$memcached" rev-parse HEAD)" > "$work/source-revisions.txt"
