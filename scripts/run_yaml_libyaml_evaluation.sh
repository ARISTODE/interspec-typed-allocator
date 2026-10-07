#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
if [[ $# -ge 1 ]]; then
  out=$1
else
  out="$root/yaml-libyaml-results"
fi
rm -rf "$out"
mkdir -p "$out"
out=$(cd "$out" && pwd)

work="${TMPDIR:-/tmp}/interspec-yaml-libyaml"
rm -rf "$work"

git clone -q https://github.com/PLSysSec/rlbox_wasm2c_sandbox.git "$work"
git -C "$work" checkout -q c4f18c48cea47421617f72ba5edc95c68aa85671
python3 "$root/backends/rlbox_wasm2c/apply_backend.py" --root "$work"

yaml_src="$work/c_src/libyaml-src"
git clone -q https://github.com/yaml/libyaml.git "$yaml_src"
git -C "$yaml_src" checkout -q 90a56d4500aa1a1798514c5cb55c3ad4cb095f94
cat > "$yaml_src/include/config.h" <<'EOF'
#define YAML_VERSION_MAJOR 0
#define YAML_VERSION_MINOR 2
#define YAML_VERSION_PATCH 5
#define YAML_VERSION_STRING "0.2.5"
EOF
cp "$yaml_src/include/config.h" "$yaml_src/src/config.h"

generated="$work/interspec-yaml-eval-generated"
python3 "$root/tools/generate_wasm_boundary_policy.py" \
  --policy "$root/integration/yaml_libyaml/policy.json" \
  --boundary "$root/integration/yaml_libyaml/boundary.json" \
  --source "$yaml_src/src/api.c" \
  --out-dir "$generated" \
  --namespace "interspec::yaml_libyaml_generated" \
  --site-id-base 0x00300000

cp "$generated/interspec_u_policy.h" "$work/c_src/interspec_yaml_u_policy.h"
cp "$generated/interspec_t_policy.h" "$work/interspec_yaml_t_policy.h"
cp "$generated/interspec_wasm_imports.c" "$work/src/interspec_yaml_wasm_imports.c"
cp "$root/integration/yaml_libyaml/yaml_app_wasm.c" "$work/c_src/yaml_app_wasm.c"

python3 - "$work/CMakeLists.txt" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()

old = 'set(C_SOURCE_FILES "${CMAKE_SOURCE_DIR}/c_src/wasm2c_sandbox_wrapper.c")'
new = r'''file(GLOB INTERSPEC_YAML_SOURCES "${CMAKE_SOURCE_DIR}/c_src/libyaml-src/src/*.c")
set(C_SOURCE_FILES
    "${CMAKE_SOURCE_DIR}/c_src/wasm2c_sandbox_wrapper.c"
    "${CMAKE_SOURCE_DIR}/c_src/yaml_app_wasm.c"
    ${INTERSPEC_YAML_SOURCES})'''
if old not in s:
    raise SystemExit("yaml evaluation could not find C_SOURCE_FILES")
s = s.replace(old, new, 1)

source = '${CMAKE_SOURCE_DIR}/c_src/wasm2c_sandbox_wrapper.c\n                            ${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c'
replacement = '${C_SOURCE_FILES}\n                            ${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c'
if s.count(source) != 2:
    raise SystemExit("yaml evaluation unexpected wasm source command count")
s = s.replace(source, replacement)

flag = '                            -O3\n'
extra = '''                            -O3
                            -I${CMAKE_SOURCE_DIR}/c_src
                            -I${CMAKE_SOURCE_DIR}/c_src/libyaml-src/include
                            -I${CMAKE_SOURCE_DIR}/c_src/libyaml-src/src
                            -DHAVE_CONFIG_H=1
'''
if s.count(flag) != 2:
    raise SystemExit("yaml evaluation unexpected compile flag count")
s = s.replace(flag, extra)

needle = '''set(WASM2C_RUNTIME_CODE ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-impl.c
                        ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-mem-impl.c
                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_minwasi.c
                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_mem.c)'''
replacement = '''set(WASM2C_RUNTIME_CODE ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-impl.c
                        ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-mem-impl.c
                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_minwasi.c
                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_mem.c
                        ${CMAKE_SOURCE_DIR}/src/interspec_yaml_wasm_imports.c)'''
if needle not in s:
    raise SystemExit("yaml evaluation could not find wasm runtime list")
p.write_text(s.replace(needle, replacement, 1))
PY

cmake -S "$work" -B "$work/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$work/build" --target glue_lib_imported --parallel 2 >/dev/null
baseline_wasm=$(find "$work/build" -name 'libglue_lib_imported.a' -print -quit)
test -n "$baseline_wasm"
baseline_snapshot="$work/libyaml-rlbox-baseline.a"
cp "$baseline_wasm" "$baseline_snapshot"

python3 - "$work/c_src/yaml_app_wasm.c" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
p.write_text("#define INTERSPEC_YAML_TYPED_COPY 1\n" + p.read_text())
PY
cmake --build "$work/build" --target glue_lib_imported --parallel 2 >/dev/null
typed_wasm=$(find "$work/build" -name 'libglue_lib_imported.a' -print -quit)
test -n "$typed_wasm"
typed_snapshot="$work/libyaml-interspec.a"
cp "$typed_wasm" "$typed_snapshot"

native_obj="$work/native-obj"
mkdir -p "$native_obj"
for src in "$yaml_src"/src/*.c; do
  stem=$(basename "$src" .c)
  cc -O3 -DHAVE_CONFIG_H=1 \
    -I"$yaml_src/include" -I"$yaml_src/src" \
    -c "$src" -o "$native_obj/$stem.o"
done
ar rcs "$work/libyaml-native.a" "$native_obj"/*.o

g++ -std=c++17 -O2 \
  "$root/integration/yaml_libyaml/yaml_native_bench.cpp" \
  -I"$yaml_src/include" "$work/libyaml-native.a" \
  -o "$work/yaml-native-bench"

g++ -std=c++17 -O2 \
  "$root/integration/yaml_libyaml/yaml_app_bench.cpp" \
  -I"$work/include" \
  -I"$work/build/_deps/rlbox-src/code/include" \
  -I"$work/build/_deps/wasm2c_compiler-src/wasm2c" \
  -I"$work/build/_deps/wasm2c_compiler-src/third_party/simde" \
  -I"$work/build/wasm_imported" \
  -I"$root/include" -I"$yaml_src/include" -I"$work" \
  "$baseline_snapshot" -pthread -ldl -lrt -lm \
  -o "$work/yaml-rlbox-bench"

g++ -std=c++17 -O2 \
  "$root/integration/yaml_libyaml/yaml_app_bench.cpp" \
  -I"$work/include" \
  -I"$work/build/_deps/rlbox-src/code/include" \
  -I"$work/build/_deps/wasm2c_compiler-src/wasm2c" \
  -I"$work/build/_deps/wasm2c_compiler-src/third_party/simde" \
  -I"$work/build/wasm_imported" \
  -I"$root/include" -I"$yaml_src/include" -I"$work" \
  "$typed_snapshot" -pthread -ldl -lrt -lm \
  -o "$work/yaml-typed-bench"

commit=$(git -C "$root" rev-parse HEAD)
python3 "$root/tools/run_yaml_libyaml_benchmarks.py" \
  --native "$work/yaml-native-bench" \
  --rlbox "$work/yaml-rlbox-bench" \
  --typed "$work/yaml-typed-bench" \
  --out "$out" \
  --commit "$commit"

echo "InterSpec YAML/libyaml full application evaluation passed"
