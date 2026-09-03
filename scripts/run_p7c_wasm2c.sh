#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-p7c-wasm2c
rm -rf "$work"

git clone -q https://github.com/PLSysSec/rlbox_wasm2c_sandbox.git "$work"
git -C "$work" checkout -q c4f18c48cea47421617f72ba5edc95c68aa85671
python3 "$root/backends/rlbox_wasm2c/apply_backend.py" --root "$work"

# ---------------------------------------------------------------------------
# memcached / bipbuffer: one precise direct malloc site plus a helper site.
# ---------------------------------------------------------------------------
memcached_src="$work/c_src/memcached-src"
git clone -q https://github.com/memcached/memcached.git "$memcached_src"
git -C "$memcached_src" checkout -q 2d51e364799bc9698bd4b11728ea978cea12da6e

bip_generated="$work/interspec-bipbuffer-generated"
python3 "$root/tools/generate_wasm_boundary_policy.py" \
  --policy "$root/integration/memcached_bipbuffer/policy.json" \
  --boundary "$root/integration/memcached_bipbuffer/boundary.json" \
  --source "$memcached_src/bipbuffer.c" \
  --out-dir "$bip_generated" \
  --namespace "interspec::memcached_bipbuffer_generated"
python3 - "$bip_generated/bipbuffer.c" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
needle = '#include "bipbuffer.h"\n'
assert needle in s
p.write_text(s.replace(needle, needle + '#include "interspec_bipbuffer_u_policy.h"\n', 1))
PY
cp "$bip_generated/bipbuffer.c" "$memcached_src/bipbuffer.c"
cp "$bip_generated/interspec_u_policy.h" "$work/c_src/interspec_bipbuffer_u_policy.h"
cp "$bip_generated/interspec_t_policy.h" "$work/interspec_bipbuffer_t_policy.h"
cp "$bip_generated/interspec_wasm_imports.c" "$work/src/interspec_bipbuffer_wasm_imports.c"
cp "$root/integration/memcached_bipbuffer/bipbuffer_smoke_wasm.c" "$work/c_src/"

# ---------------------------------------------------------------------------
# nginx / libpcre: PCRE's allocator abstraction is an explicit helper site.
# ---------------------------------------------------------------------------
pcre_src="$work/c_src/pcre-src"
git clone -q https://github.com/nektro/pcre-8.45.git "$pcre_src"
git -C "$pcre_src" checkout -q e67dabe61b327bd2d888954b0e74a7c9cfd0a195

pcre_generated="$work/interspec-pcre-generated"
python3 "$root/tools/generate_wasm_boundary_policy.py" \
  --policy "$root/integration/nginx_libpcre/policy.json" \
  --boundary "$root/integration/nginx_libpcre/boundary.json" \
  --source "$pcre_src/pcre_compile.c" \
  --out-dir "$pcre_generated" \
  --namespace "interspec::nginx_libpcre_generated"
python3 - "$pcre_generated/pcre_compile.c" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
inc = '#include "pcre_internal.h"\n'
assert inc in s
s = s.replace(inc, inc + '#include <stdint.h>\n#include "interspec_pcre_u_policy.h"\n', 1)
old = 're = (REAL_PCRE *)(PUBL(malloc))(size);'
new = 're = (REAL_PCRE *)(uintptr_t)INTERSPEC_SITE_COMPILED_REGEX_ALLOC((uint32_t)size);'
assert old in s
p.write_text(s.replace(old, new, 1))
PY
cp "$pcre_generated/pcre_compile.c" "$pcre_src/pcre_compile.c"
cp "$pcre_generated/interspec_u_policy.h" "$work/c_src/interspec_pcre_u_policy.h"
cp "$pcre_generated/interspec_t_policy.h" "$work/interspec_pcre_t_policy.h"
cp "$pcre_generated/interspec_wasm_imports.c" "$work/src/interspec_pcre_wasm_imports.c"
cp "$root/integration/nginx_libpcre/pcre_smoke_wasm.c" "$work/c_src/"

# ---------------------------------------------------------------------------
# yaml / libyaml: scalar value allocation is an explicit helper site.
# ---------------------------------------------------------------------------
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

yaml_generated="$work/interspec-yaml-generated"
python3 "$root/tools/generate_wasm_boundary_policy.py" \
  --policy "$root/integration/yaml_libyaml/policy.json" \
  --boundary "$root/integration/yaml_libyaml/boundary.json" \
  --source "$yaml_src/src/api.c" \
  --out-dir "$yaml_generated" \
  --namespace "interspec::yaml_libyaml_generated"
python3 - "$yaml_generated/api.c" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
inc = '#include "yaml_private.h"\n'
assert inc in s
s = s.replace(inc, inc + '#include <stdint.h>\n#include "interspec_yaml_u_policy.h"\n', 1)
old = 'value_copy = YAML_MALLOC(length+1);'
new = 'value_copy = (yaml_char_t *)(uintptr_t)INTERSPEC_SITE_SCALAR_VALUE_ALLOC((uint32_t)(length + 1));'
assert s.count(old) >= 2
p.write_text(s.replace(old, new, 1))
PY
cp "$yaml_generated/api.c" "$yaml_src/src/api.c"
cp "$yaml_generated/interspec_u_policy.h" "$work/c_src/interspec_yaml_u_policy.h"
cp "$yaml_generated/interspec_t_policy.h" "$work/interspec_yaml_t_policy.h"
cp "$yaml_generated/interspec_wasm_imports.c" "$work/src/interspec_yaml_wasm_imports.c"
cp "$root/integration/yaml_libyaml/yaml_smoke_wasm.c" "$work/c_src/"

# Each generated import file contains the shared release/size/reallocate imports.
# Keep one copy and strip those common definitions from the other two files.
python3 - "$work/src/interspec_pcre_wasm_imports.c" "$work/src/interspec_yaml_wasm_imports.c" <<'PY'
from pathlib import Path
import sys
marker = 'uint32_t w2c_env_interspecWasmRelease'
for name in sys.argv[1:]:
    p = Path(name)
    s = p.read_text()
    assert marker in s
    p.write_text(s[:s.index(marker)])
PY

# Add all three real boundaries to the pinned wasm2c module.
python3 - "$work/CMakeLists.txt" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
old = 'set(C_SOURCE_FILES "${CMAKE_SOURCE_DIR}/c_src/wasm2c_sandbox_wrapper.c")'
new = r'''set(INTERSPEC_PCRE_SOURCES
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_byte_order.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_chartables.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_compile.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_config.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_dfa_exec.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_exec.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_fullinfo.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_get.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_globals.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_maketables.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_newline.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_ord2utf8.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_refcount.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_string_utils.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_study.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_tables.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_ucd.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_valid_utf8.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_version.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre-src/pcre_xclass.c")
file(GLOB INTERSPEC_YAML_SOURCES "${CMAKE_SOURCE_DIR}/c_src/libyaml-src/src/*.c")
set(C_SOURCE_FILES
    "${CMAKE_SOURCE_DIR}/c_src/wasm2c_sandbox_wrapper.c"
    "${CMAKE_SOURCE_DIR}/c_src/memcached-src/bipbuffer.c"
    "${CMAKE_SOURCE_DIR}/c_src/bipbuffer_smoke_wasm.c"
    "${CMAKE_SOURCE_DIR}/c_src/pcre_smoke_wasm.c"
    "${CMAKE_SOURCE_DIR}/c_src/yaml_smoke_wasm.c"
    ${INTERSPEC_PCRE_SOURCES}
    ${INTERSPEC_YAML_SOURCES})'''
assert old in s
s = s.replace(old, new, 1)
source = '${CMAKE_SOURCE_DIR}/c_src/wasm2c_sandbox_wrapper.c\n                            ${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c'
replacement = '${C_SOURCE_FILES}\n                            ${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c'
assert s.count(source) == 2
s = s.replace(source, replacement)
flag = '                            -O3\n'
extra = '''                            -O3
                            -I${CMAKE_SOURCE_DIR}/c_src
                            -I${CMAKE_SOURCE_DIR}/c_src/memcached-src
                            -I${CMAKE_SOURCE_DIR}/c_src/pcre-src
                            -I${CMAKE_SOURCE_DIR}/c_src/libyaml-src/include
                            -I${CMAKE_SOURCE_DIR}/c_src/libyaml-src/src
                            -DHAVE_CONFIG_H=1
'''
assert s.count(flag) == 2
s = s.replace(flag, extra)
needle = 'set(WASM2C_RUNTIME_CODE ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-impl.c\n                        ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-mem-impl.c\n                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_minwasi.c\n                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_mem.c)'
replacement = '''set(WASM2C_RUNTIME_CODE ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-impl.c
                        ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-mem-impl.c
                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_minwasi.c
                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_mem.c
                        ${CMAKE_SOURCE_DIR}/src/interspec_bipbuffer_wasm_imports.c
                        ${CMAKE_SOURCE_DIR}/src/interspec_pcre_wasm_imports.c
                        ${CMAKE_SOURCE_DIR}/src/interspec_yaml_wasm_imports.c)'''
assert needle in s
p.write_text(s.replace(needle, replacement, 1))
PY

cmake -S "$work" -B "$work/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/build" --target glue_lib_imported --parallel 2
wasm_lib=$(find "$work/build" -name 'libglue_lib_imported.a' -print -quit)
test -n "$wasm_lib"

common_includes=(
  -I"$work/include"
  -I"$work/build/_deps/rlbox-src/code/include"
  -I"$work/build/_deps/wasm2c_compiler-src/wasm2c"
  -I"$work/build/_deps/wasm2c_compiler-src/third_party/simde"
  -I"$work/build/wasm_imported"
  -I"$root/include"
  -I"$work"
)

g++ -std=c++17 -O2 \
  "$root/integration/p7c_wasm_smoke.cpp" \
  "${common_includes[@]}" "$wasm_lib" -pthread -ldl -lrt -lm \
  -o "$work/p7c-wasm-smoke"
"$work/p7c-wasm-smoke"

echo "InterSpec P10: memcached/bipbuffer passed in RLBox wasm2c"
echo "InterSpec P10: nginx/libpcre passed in RLBox wasm2c"
echo "InterSpec P10: yaml/libyaml passed in RLBox wasm2c"
echo "InterSpec P10: all P7c generalization boundaries passed on wasm2c"
