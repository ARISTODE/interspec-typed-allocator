#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${INTERSPEC_MEMCACHED_WORK:-${TMPDIR:-/tmp}/interspec-memcached-deployment}
deps=${INTERSPEC_WASM_DEPS:-$work/wasm-deps}
src="$work/upstream"
generated="$work/generated"
[[ -f "$work/build-manifest.json" ]]
[[ $(git -C "$src" rev-parse HEAD) == 2d51e364799bc9698bd4b11728ea978cea12da6e ]]
[[ $(git -C "$deps" rev-parse HEAD) == c4f18c48cea47421617f72ba5edc95c68aa85671 ]]
wabt="$deps/build/_deps/wasm2c_compiler-src"
wasi="$deps/build/_deps/wasiclang-src"
[[ $(git -C "$wabt" rev-parse HEAD) == 974221b1ef82f6393d004e5da6116f2ad3e44005 ]]
[[ $(git -C "$deps/build/_deps/rlbox-src" rev-parse HEAD) == b0157dc84f86ffbe4549e32ed5cbdfad79c17f43 ]]
includes=(-I"$deps/include" -I"$deps/build/_deps/rlbox-src/code/include"
  -I"$wabt/wasm2c" -I"$wabt/third_party/simde" -I"$generated" -I"$root/include" -I"$src")
defines=(-DWASM_RT_USE_MMAP=1 -DWASM_RT_SKIP_SIGNAL_RECOVERY=1 -DWASM_RT_NONCONFORMING_UNCHECKED_STACK_EXHAUSTION=1)
outbase="$work/boundary-bench"
mkdir -p "$outbase"
cc -O2 -I"$src" -c "$src/bipbuffer.c" -o "$outbase/native-buffer.o"
cc -O2 -c "$root/evaluation/native_empty_call.c" -o "$outbase/native-empty.o"
g++ -std=c++17 -O2 -pthread -DINTERSPEC_NATIVE_BENCH=1 -I"$src" \
  "$root/evaluation/memcached_boundary_bench.cpp" "$outbase/native-buffer.o" "$outbase/native-empty.o" \
  -o "$outbase/native"

# Separate modules export a no-op only for this experiment. Server modules and
# release binary identities are untouched. Both use identical pinned sources.
for module in ordinary typed; do
  out="$outbase/$module-module"
  mkdir -p "$out"
  if [[ $module == ordinary ]]; then
    bip_source="$src/bipbuffer.c"; tracking=0
  else
    bip_source="$generated/bipbuffer.c"; tracking=1
  fi
  "$wasi/bin/clang" --sysroot "$wasi/share/wasi-sysroot" -O3 \
    -I"$src" -I"$generated" -DINTERSPEC_TRACKING="$tracking" -DINTERSPEC_BOUNDARY_BENCH=1 \
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
for variant in rlbox-only tracked-no-check interspec; do
  module=typed; tracking=1; checks=0
  [[ $variant != rlbox-only ]] || { module=ordinary; tracking=0; }
  [[ $variant != interspec ]] || checks=1
  g++ -std=c++17 -O2 -g "${defines[@]}" "${includes[@]}" -I"$outbase/$module-module" \
    -DINTERSPEC_BOUNDARY_BENCH=1 -DINTERSPEC_TRACKING="$tracking" -DINTERSPEC_CHECKS="$checks" \
    "$root/evaluation/memcached_boundary_bench.cpp" "$root/integration/memcached_server/bridge.cpp" \
    "$outbase/$module-module/module.a" -pthread -ldl -lrt -lm -o "$outbase/$variant"
done
python3 - "$root" "$outbase" <<'PY'
import hashlib,json,subprocess,sys
from pathlib import Path
root,out=map(Path,sys.argv[1:])
variants=('native','rlbox-only','tracked-no-check','interspec')
paths=('integration/memcached_server/bridge.cpp','integration/memcached_server/bipbuffer_u.c',
       'evaluation/native_empty_call.c','evaluation/memcached_boundary_bench.cpp',
       'scripts/build_memcached_boundary_bench.sh')
manifest=dict(source_commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),
              source_dirty=bool(subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'])),
              binary_sha256={v:hashlib.sha256((out/v).read_bytes()).hexdigest() for v in variants},
              source_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},
              cflags='-O2; WASI -O3; no LTO; diagnostics and faults disabled')
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
PY
