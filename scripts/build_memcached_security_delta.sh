#!/usr/bin/env bash
# Fault-capable, sanitizer-instrumented T comparators; never benchmark these.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${INTERSPEC_MEMCACHED_WORK:-${TMPDIR:-/tmp}/interspec-memcached-deployment}
jobs=${INTERSPEC_BUILD_JOBS:-2}

INTERSPEC_SECURITY_DELTA_BUILD=1 bash "$root/scripts/build_memcached_deployment.sh"

asan_flags=(-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all)
asan_cflags='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all'
asan_ldflags='-fsanitize=address,undefined'
upstream="$work/upstream"
revision=2d51e364799bc9698bd4b11728ea978cea12da6e
deps=${INTERSPEC_WASM_DEPS:-$work/wasm-deps}
wabt="$deps/build/_deps/wasm2c_compiler-src"
includes=(-I"$deps/include" -I"$deps/build/_deps/rlbox-src/code/include"
  -I"$wabt/wasm2c" -I"$wabt/third_party/simde" -I"$work/generated" -I"$root/include" -I"$upstream")
defines=(-DWASM_RT_USE_MMAP=1 -DWASM_RT_SKIP_SIGNAL_RECOVERY=1
  -DWASM_RT_NONCONFORMING_UNCHECKED_STACK_EXHAUSTION=1)

native="$work/security-asan/native"
if [[ ! -f "$native/Makefile" ]]; then
  mkdir -p "$native"
  (cd "$native" && "$upstream/configure" --disable-extstore --disable-proxy \
    --disable-docs CFLAGS="$asan_cflags" LDFLAGS="$asan_ldflags") \
    > "$work/logs/security-native-configure.log" 2>&1
fi
make -C "$native" -j"$jobs" memcached > "$work/logs/security-native-build.log" 2>&1
host_objects=()
for object in "$native"/memcached-*.o; do
  case $(basename "$object") in
    memcached-bipbuffer.o|memcached-logger.o|memcached-items.o) ;;
    *) host_objects+=("$object");;
  esac
done
[[ ${#host_objects[@]} -gt 10 ]]

# Source variants differ only in LRU wire-pointer handling. They are all
# constructed from the same pinned upstream revision and with identical T
# sanitizers; the existing handle adapter is the fourth H2 comparator.
for mode in handle upstream domain extended; do
  server="$work/security-asan/$mode"
  if [[ ! -f "$server/configure" ]]; then cp -a "$upstream" "$server"; fi
  git -C "$upstream" show "$revision:logger.c" > "$server/logger.c"
  git -C "$upstream" show "$revision:items.c" > "$server/items.c"
  python3 "$root/tools/prepare_memcached_deployment.py" \
    --source "$server" --root "$root" --lru-mode "$mode"
  if [[ ! -f "$server/Makefile" ]]; then
    (cd "$server" && ./configure --disable-extstore --disable-proxy \
      --disable-docs CFLAGS="$asan_cflags" LDFLAGS="$asan_ldflags") \
      > "$work/logs/security-$mode-configure.log" 2>&1
  fi
  make -C "$server" -j"$jobs" memcached-logger.o memcached-items.o \
    > "$work/logs/security-$mode-build.log" 2>&1
done

variants=(h1-rlbox h1-extended h2-upstream h2-domain h2-extended)
for variant in "${variants[@]}"; do
  mode=handle
  module=fault-ordinary
  flags=(-DINTERSPEC_TRACKING=0 -DINTERSPEC_CHECKS=0)
  case "$variant" in
    h1-rlbox) ;;
    h1-extended) module=fault; flags=(-DINTERSPEC_TRACKING=1 -DINTERSPEC_CHECKS=1);;
    h2-upstream) mode=upstream;;
    h2-domain) mode=domain;;
    h2-extended) mode=extended; flags+=(-DINTERSPEC_T_OBJECTS=1);;
  esac
  server="$work/security-asan/$mode"
  g++ -std=c++17 "${asan_flags[@]}" "${defines[@]}" "${flags[@]}" \
    -DINTERSPEC_ENABLE_TRACE=1 -DINTERSPEC_FAULT_TESTS=1 \
    "${includes[@]}" -I"$work/$module" \
    -c "$root/integration/memcached_server/bridge.cpp" \
    -o "$work/security-asan/$variant-bridge.o"
  g++ "${asan_flags[@]}" "${host_objects[@]}" \
    "$server/memcached-logger.o" "$server/memcached-items.o" \
    "$work/security-asan/$variant-bridge.o" "$work/$module/module.a" \
    -levent -pthread -ldl -lrt -lm \
    -o "$work/bin/memcached-$variant.new"
  mv "$work/bin/memcached-$variant.new" "$work/bin/memcached-$variant"
done
cp "$work/bin/memcached-h1-extended" "$work/bin/memcached-h2-handle"

python3 - "$root" "$work" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root, work = map(Path, sys.argv[1:])
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

names = ["h1-rlbox", "h1-extended", "h2-upstream", "h2-domain", "h2-extended", "h2-handle"]
manifest = {
    "schema": 1,
    "project_commit": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
    "source_dirty": bool(subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"])),
    "memcached_revision": subprocess.check_output(["git", "-C", str(work / "upstream"), "rev-parse", "HEAD"], text=True).strip(),
    "comparators": {name: sha(work / "bin" / f"memcached-{name}") for name in names},
    "host_instrumentation": ["AddressSanitizer", "UndefinedBehaviorSanitizer"],
    "timing_permitted": False,
}
(work / "security-asan" / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY
echo "Built sanitizer-only SP3 security-delta comparators in $work/bin"
