#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${INTERSPEC_MEMCACHED_WORK:-${TMPDIR:-/tmp}/interspec-memcached-deployment}
deps=${INTERSPEC_WASM_DEPS:-$work/wasm-deps}
jobs=${INTERSPEC_BUILD_JOBS:-2}
revision=2d51e364799bc9698bd4b11728ea978cea12da6e
mkdir -p "$work/bin" "$work/logs"

# An explicit cache may reuse the already pinned P9/P10 backend/toolchain.
# Otherwise bootstrap only the small upstream glue library, not P7c's PCRE/YAML.
if [[ ! -d "$deps/.git" ]]; then
  git clone -q https://github.com/PLSysSec/rlbox_wasm2c_sandbox.git "$deps"
  git -C "$deps" checkout -q c4f18c48cea47421617f72ba5edc95c68aa85671
  python3 "$root/backends/rlbox_wasm2c/apply_backend.py" --root "$deps"
fi
[[ $(git -C "$deps" rev-parse HEAD) == c4f18c48cea47421617f72ba5edc95c68aa85671 ]]
if [[ ! -f "$deps/build/libglue_lib_imported.a" ]]; then
  cmake -S "$deps" -B "$deps/build" -DCMAKE_BUILD_TYPE=Release > "$work/logs/deps-configure.log" 2>&1
  cmake --build "$deps/build" --target glue_lib_imported -j"$jobs" > "$work/logs/deps-build.log" 2>&1
fi
[[ $(git -C "$deps/build/_deps/rlbox-src" rev-parse HEAD) == b0157dc84f86ffbe4549e32ed5cbdfad79c17f43 ]]
[[ $(git -C "$deps/build/_deps/wasm2c_compiler-src" rev-parse HEAD) == 974221b1ef82f6393d004e5da6116f2ad3e44005 ]]
src="$work/upstream"
if [[ ! -d "$src/.git" ]]; then
  git clone -q https://github.com/memcached/memcached.git "$src"
  git -C "$src" checkout -q "$revision"
  (cd "$src" && ./autogen.sh) > "$work/logs/autogen.log" 2>&1
fi
[[ $(git -C "$src" rev-parse HEAD) == "$revision" ]]
if [[ ! -f "$work/native/Makefile" ]]; then
  mkdir -p "$work/native"
  (cd "$work/native" && "$src/configure" --disable-extstore --disable-proxy --disable-docs CFLAGS='-O2 -g') > "$work/logs/native-configure.log" 2>&1
fi
make -C "$work/native" -j"$jobs" memcached memcached-debug timedrun > "$work/logs/native-build.log" 2>&1
cp "$work/native/memcached" "$work/bin/memcached-native.new"
mv "$work/bin/memcached-native.new" "$work/bin/memcached-native"
cp "$work/native/memcached-debug" "$work/bin/memcached-native-debug.new"
mv "$work/bin/memcached-native-debug.new" "$work/bin/memcached-native-debug"

# Build the unchanged server except for the library bridge and log-data checks.
if [[ ! -d "$work/server" ]]; then cp -a "$src" "$work/server"; fi
git -C "$src" show "$revision:logger.c" > "$work/server/logger.c"
git -C "$src" show "$revision:items.c" > "$work/server/items.c"
python3 "$root/tools/prepare_memcached_deployment.py" --source "$work/server" --root "$root"
if [[ ! -f "$work/server/Makefile" ]]; then
  (cd "$work/server" && ./configure --disable-extstore --disable-proxy --disable-docs CFLAGS='-O2 -g') > "$work/logs/server-configure.log" 2>&1
fi
make -C "$work/server" -j"$jobs" memcached-logger.o memcached_debug-logger.o memcached-items.o memcached_debug-items.o > "$work/logs/server-build.log" 2>&1

generated="$work/generated"
python3 "$root/tools/generate_wasm_boundary_policy.py" \
  --policy "$root/integration/memcached_bipbuffer/policy.json" \
  --boundary "$root/integration/memcached_bipbuffer/boundary.json" \
  --source "$src/bipbuffer.c" --out-dir "$generated" \
  --namespace 'interspec::memcached_bipbuffer_generated' --site-id-base 0x00100000
cp "$generated/interspec_u_policy.h" "$generated/interspec_bipbuffer_u_policy.h"
cp "$generated/interspec_t_policy.h" "$generated/interspec_bipbuffer_t_policy.h"
python3 - "$generated/bipbuffer.c" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1]); s = p.read_text()
s = s.replace('#include "bipbuffer.h"', '#include "bipbuffer.h"\n#include "interspec_bipbuffer_u_policy.h"', 1)
assert s.count('    free(me);') == 1
s = s.replace('    free(me);', '    interspec_wasm_release((uint32_t)(uintptr_t)me);', 1)
p.write_text(s)
PY

wabt="$deps/build/_deps/wasm2c_compiler-src"
wasi="$deps/build/_deps/wasiclang-src"
includes=(-I"$deps/include" -I"$deps/build/_deps/rlbox-src/code/include"
  -I"$wabt/wasm2c" -I"$wabt/third_party/simde" -I"$generated" -I"$root/include" -I"$src")
defines=(-DWASM_RT_USE_MMAP=1 -DWASM_RT_SKIP_SIGNAL_RECOVERY=1 -DWASM_RT_NONCONFORMING_UNCHECKED_STACK_EXHAUSTION=1)

for module in ordinary typed fault; do
  out="$work/$module"
  mkdir -p "$out"
  flags=()
  if [[ $module == ordinary ]]; then
    bip_source="$src/bipbuffer.c"; flags+=(-DINTERSPEC_TRACKING=0)
  else
    bip_source="$generated/bipbuffer.c"; flags+=(-DINTERSPEC_TRACKING=1)
  fi
  [[ $module != fault ]] || flags+=(-DINTERSPEC_FAULT_TESTS=1)
  "$wasi/bin/clang" --sysroot "$wasi/share/wasi-sysroot" -O3 \
    -I"$src" -I"$generated" "${flags[@]}" \
    -Wl,--export-all -Wl,--no-entry -Wl,--growable-table -Wl,--stack-first -Wl,-z,stack-size=1048576 -Wl,--import-memory -Wl,--import-table \
    "$deps/c_src/wasm2c_sandbox_wrapper.c" "$bip_source" "$root/integration/memcached_server/bipbuffer_u.c" \
    -o "$out/glue_lib_wasm2c.wasm"
  "$wabt/build_release/wasm2c" -o "$out/glue_lib_wasm2c.c" "$out/glue_lib_wasm2c.wasm"
  sources=("$out/glue_lib_wasm2c.c" "$wabt/wasm2c/wasm-rt-impl.c" "$wabt/wasm2c/wasm-rt-mem-impl.c"
    "$deps/src/wasm2c_rt_minwasi.c" "$deps/src/wasm2c_rt_mem.c")
  [[ $module == ordinary ]] || sources+=("$generated/interspec_wasm_imports.c")
  objects=()
  for source in "${sources[@]}"; do
    obj="$out/$(basename "${source%.c}").o"
    cc -O2 -std=gnu11 "${defines[@]}" "${includes[@]}" -I"$out" -c "$source" -o "$obj"
    objects+=("$obj")
  done
  ar rcs "$out/module.a" "${objects[@]}"
done
if grep -q 'interspecWasm' "$work/ordinary/glue_lib_wasm2c.h"; then
  echo 'RLBox-only module unexpectedly imports typed allocation' >&2; exit 1
fi
if grep -q 'interspec_mc_fault' "$work/typed/glue_lib_wasm2c.h"; then
  echo 'Release module unexpectedly contains fault hooks' >&2; exit 1
fi

server_objects=()
for obj in "$work/native"/memcached-*.o; do
  [[ $(basename "$obj") != memcached-bipbuffer.o && $(basename "$obj") != memcached-logger.o && $(basename "$obj") != memcached-items.o ]] || continue
  server_objects+=("$obj")
done
server_objects+=("$work/server/memcached-logger.o" "$work/server/memcached-items.o")
for variant in rlbox-only tracked-no-check interspec diagnostics; do
  module=typed
  flags=(-DINTERSPEC_TRACKING=1 -DINTERSPEC_CHECKS=0)
  case $variant in
    rlbox-only) module=ordinary; flags=(-DINTERSPEC_TRACKING=0 -DINTERSPEC_CHECKS=0);;
    interspec) flags=(-DINTERSPEC_TRACKING=1 -DINTERSPEC_CHECKS=1);;
    diagnostics) module=fault; flags=(-DINTERSPEC_TRACKING=1 -DINTERSPEC_CHECKS=1 -DINTERSPEC_ENABLE_TRACE=1 -DINTERSPEC_FAULT_TESTS=1);;
  esac
  g++ -std=c++17 -O2 -g "${defines[@]}" "${flags[@]}" "${includes[@]}" -I"$work/$module" \
    -c "$root/integration/memcached_server/bridge.cpp" -o "$work/$variant-bridge.o"
  g++ "${server_objects[@]}" "$work/$variant-bridge.o" "$work/$module/module.a" \
    -levent -pthread -ldl -lrt -lm -o "$work/bin/memcached-$variant.new"
  mv "$work/bin/memcached-$variant.new" "$work/bin/memcached-$variant"
done
debug_objects=()
for obj in "$work/native"/memcached_debug-*.o; do
  [[ $(basename "$obj") != memcached_debug-bipbuffer.o && $(basename "$obj") != memcached_debug-logger.o && $(basename "$obj") != memcached_debug-items.o ]] || continue
  debug_objects+=("$obj")
done
g++ "${debug_objects[@]}" "$work/server/memcached_debug-logger.o" "$work/server/memcached_debug-items.o" "$work/interspec-bridge.o" "$work/typed/module.a" \
  --coverage -levent -pthread -ldl -lrt -lm -o "$work/bin/memcached-interspec-debug.new"
mv "$work/bin/memcached-interspec-debug.new" "$work/bin/memcached-interspec-debug"
python3 - "$work" "$root" "$deps" <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
work, root, deps = map(Path, sys.argv[1:])
def rev(path): return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
info = {'project_commit': rev(root), 'project_dirty': bool(subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'])),
        'memcached_revision': rev(work/'upstream'), 'rlbox_wasm2c_revision': rev(deps),
        'configure': ['--disable-extstore', '--disable-proxy', '--disable-docs'],
        'host_cflags': '-O2 -g', 'wasm_cflags': '-O3',
        'bridge_source_sha256': hashlib.sha256((root/'integration/memcached_server/bridge.cpp').read_bytes()).hexdigest(),
        'untrusted_source_sha256': hashlib.sha256((root/'integration/memcached_server/bipbuffer_u.c').read_bytes()).hexdigest(),
        'generated_policy_sha256': hashlib.sha256((work/'generated/interspec_t_policy.h').read_bytes()).hexdigest(),
        'binary_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((work/'bin').glob('memcached-*'))}}
(work/'build-manifest.json').write_text(json.dumps(info, indent=2)+'\n')
PY
echo "Built memcached variants in $work/bin"
