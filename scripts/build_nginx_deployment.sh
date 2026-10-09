#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${INTERSPEC_NGINX_WORK:-${TMPDIR:-/tmp}/interspec-nginx-deployment}
deps=${INTERSPEC_WASM_DEPS:-$work/wasm-deps}
jobs=${INTERSPEC_BUILD_JOBS:-2}
nginx_revision=1be0fb0c9f9bc3489c7b40576efd6afe6b2eccd5
pcre_revision=e67dabe61b327bd2d888954b0e74a7c9cfd0a195
mkdir -p "$work/bin" "$work/logs"
checkout() {
  local url=$1 path=$2 revision=$3
  if [[ ! -d "$path/.git" ]]; then
    git clone -q "$url" "$path"
    git -C "$path" checkout -q "$revision"
  fi
  [[ $(git -C "$path" rev-parse HEAD) == "$revision" ]]
}
checkout https://github.com/PLSysSec/rlbox_wasm2c_sandbox.git "$deps" c4f18c48cea47421617f72ba5edc95c68aa85671
python3 "$root/backends/rlbox_wasm2c/apply_backend.py" --root "$deps"
if [[ ! -f "$deps/build/libglue_lib_imported.a" ]]; then
  cmake -S "$deps" -B "$deps/build" -DCMAKE_BUILD_TYPE=Release > "$work/logs/deps-configure.log" 2>&1
  cmake --build "$deps/build" --target glue_lib_imported --parallel "$jobs" > "$work/logs/deps-build.log" 2>&1
fi
[[ $(git -C "$deps/build/_deps/rlbox-src" rev-parse HEAD) == b0157dc84f86ffbe4549e32ed5cbdfad79c17f43 ]]
[[ $(git -C "$deps/build/_deps/wasm2c_compiler-src" rev-parse HEAD) == 974221b1ef82f6393d004e5da6116f2ad3e44005 ]]
checkout https://github.com/nginx/nginx.git "$work/upstream" "$nginx_revision"
checkout https://github.com/nektro/pcre-8.45.git "$work/pcre" "$pcre_revision"
pcre="$work/pcre"
generated="$work/generated"
python3 "$root/tools/generate_wasm_boundary_policy.py" \
  --policy "$root/integration/nginx_server/policy.json" \
  --boundary "$root/integration/nginx_server/boundary.json" \
  --source "$pcre/pcre_compile.c" --out-dir "$generated" \
  --namespace 'interspec::nginx_server_generated' --site-id-base 0x00400000
cp "$generated/interspec_u_policy.h" "$generated/interspec_pcre_u_policy.h"
cp "$generated/interspec_t_policy.h" "$generated/interspec_pcre_t_policy.h"
mkdir -p "$work/server"
git -C "$work/upstream" archive "$nginx_revision" | tar -x -C "$work/server"
python3 "$root/tools/prepare_nginx_deployment.py" --nginx "$work/server" --generated "$generated"

# Compile the same PCRE interpreter for Native and Wasm, with JIT disabled.
pcre_stems=(byte_order chartables compile config dfa_exec exec fullinfo get globals
  maketables newline ord2utf8 refcount string_utils study tables ucd valid_utf8 version xclass)
mkdir -p "$work/native-pcre"
native_objects=()
for stem in "${pcre_stems[@]}"; do
  cc -O3 -DHAVE_CONFIG_H=1 -I"$pcre" -c "$pcre/pcre_$stem.c" -o "$work/native-pcre/$stem.o"
  native_objects+=("$work/native-pcre/$stem.o")
done
ar rcs "$work/native-pcre/libpcre.a" "${native_objects[@]}"
for kind in native server; do
  if [[ $kind == native ]]; then
    mkdir -p "$work/native"
    git -C "$work/upstream" archive "$nginx_revision" | tar -x -C "$work/native"
  fi
  (cd "$work/$kind" && ./auto/configure --without-pcre2 --without-http_gzip_module \
    --with-cc-opt="-O2 -I$pcre" --with-ld-opt="-L$work/native-pcre" \
    --prefix="$work/prefix") > "$work/logs/$kind-configure.log" 2>&1
done
make -C "$work/native" -j"$jobs" > "$work/logs/native-build.log" 2>&1
cp "$work/native/objs/nginx" "$work/bin/nginx-native"

wabt="$deps/build/_deps/wasm2c_compiler-src"
wasi="$deps/build/_deps/wasiclang-src"
includes=(-I"$deps/include" -I"$deps/build/_deps/rlbox-src/code/include"
  -I"$wabt/wasm2c" -I"$wabt/third_party/simde" -I"$generated" -I"$root/include" -I"$pcre")
defines=(-DWASM_RT_USE_MMAP=1 -DWASM_RT_SKIP_SIGNAL_RECOVERY=1 -DWASM_RT_NONCONFORMING_UNCHECKED_STACK_EXHAUSTION=1)
# PCRE's interpreter compilation is expensive. The common library sources
# are identical in all three modules, so compile those objects exactly once.
mkdir -p "$work/common-wasm"
common_objects=()
for stem in "${pcre_stems[@]}"; do
  [[ $stem != compile ]] || continue
  obj="$work/common-wasm/$stem.o"
  "$wasi/bin/clang" --sysroot "$wasi/share/wasi-sysroot" -O3 -DHAVE_CONFIG_H=1 \
    -I"$pcre" -c "$pcre/pcre_$stem.c" -o "$obj"
  common_objects+=("$obj")
done
for module in ordinary typed fault; do
  out="$work/$module"
  mkdir -p "$out"
  flags=(-DINTERSPEC_TRACKING=1)
  [[ $module != ordinary ]] || flags=(-DINTERSPEC_TRACKING=0)
  [[ $module != fault ]] || flags+=(-DINTERSPEC_FAULT_TESTS=1)
  compile_source="$generated/pcre_compile.c"
  [[ $module != ordinary ]] || compile_source="$pcre/pcre_compile.c"
  "$wasi/bin/clang" --sysroot "$wasi/share/wasi-sysroot" -O3 -DHAVE_CONFIG_H=1 \
    -I"$pcre" -I"$generated" "${flags[@]}" \
    -Wl,--export-all -Wl,--no-entry -Wl,--growable-table -Wl,--stack-first \
    -Wl,-z,stack-size=1048576 -Wl,--import-memory -Wl,--import-table \
    "$deps/c_src/wasm2c_sandbox_wrapper.c" "${common_objects[@]}" "$compile_source" "$root/integration/nginx_server/pcre_u.c" \
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
if grep -q 'interspec_nginx_fault' "$work/typed/glue_lib_wasm2c.h"; then
  echo 'Release module unexpectedly contains fault hooks' >&2; exit 1
fi

# Link the unchanged nginx objects with the PCRE ABI bridge instead of libpcre.
python3 - "$work/server/objs/Makefile" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
assert s.count('-lpcre') == 1
s=s.replace('-lpcre', '$(INTERSPEC_BRIDGE) $(INTERSPEC_MODULE) -lstdc++ -pthread -ldl -lrt -lm')
p.write_text(s)
PY
for variant in rlbox-only tracked-no-check interspec diagnostics; do
  module=typed
  flags=(-DINTERSPEC_TRACKING=1 -DINTERSPEC_CHECKS=0)
  case $variant in
    rlbox-only) module=ordinary; flags=(-DINTERSPEC_TRACKING=0 -DINTERSPEC_CHECKS=0);;
    interspec) flags=(-DINTERSPEC_TRACKING=1 -DINTERSPEC_CHECKS=1);;
    diagnostics) module=fault; flags=(-DINTERSPEC_TRACKING=1 -DINTERSPEC_CHECKS=1 -DINTERSPEC_ENABLE_TRACE=1 -DINTERSPEC_FAULT_TESTS=1);;
  esac
  g++ -std=c++17 -O2 "${defines[@]}" "${flags[@]}" "${includes[@]}" -I"$work/$module" \
    -c "$root/integration/nginx_server/bridge.cpp" -o "$work/$variant-bridge.o"
  rm -f "$work/server/objs/nginx"
  make -C "$work/server" -j"$jobs" INTERSPEC_BRIDGE="$work/$variant-bridge.o" \
    INTERSPEC_MODULE="$work/$module/module.a" > "$work/logs/$variant-build.log" 2>&1
  cp "$work/server/objs/nginx" "$work/bin/nginx-$variant"
done
python3 - "$root" "$work" <<'PY'
import hashlib,json,subprocess,sys
from pathlib import Path
root,work=map(Path,sys.argv[1:])
def rev(p): return subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
info={'project_commit':rev(root),'project_dirty':bool(subprocess.check_output(['git','-C',str(root),'status','--porcelain'])),
 'nginx_revision':rev(work/'upstream'),'pcre_revision':rev(work/'pcre'),
 'source_sha256':{str(p.relative_to(root)):sha(p) for p in sorted((root/'integration/nginx_server').glob('*')) if p.is_file()},
 'binary_sha256':{p.name:sha(p) for p in sorted((work/'bin').glob('nginx-*'))},
 'scope':'PCRE8 interpreter; HTTP; nginx event loop; no TLS, PCRE2, JIT, or threaded third-party regex calls',
 'limits':{'subject_bytes':65536,'offset_ints':4096,'typed_arena_bytes_per_regex':1048576}}
for name in ['scripts/build_nginx_deployment.sh','tools/prepare_nginx_deployment.py','tools/generate_wasm_boundary_policy.py',
             'tools/nginx_common.py','tools/test_nginx_deployment.py','tools/benchmark_nginx.py']:
 info['source_sha256'][name]=sha(root/name)
info['generated_sha256']={p.name:sha(p) for p in sorted((work/'generated').glob('*')) if p.is_file()}
(work/'build-manifest.json').write_text(json.dumps(info,indent=2)+'\n')
PY
