#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-rlbox-nacl

if [[ ! -d "$work/c_src" || ! -d "$work/build" ]]; then
  echo "P7c YAML extension requires run_rlbox_nacl_poc.sh to complete first" >&2
  exit 1
fi

yaml_src="$work/c_src/libyaml-src"
rm -rf "$yaml_src"
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
rm -rf "$yaml_generated"
python3 "$root/tools/generate_boundary_policy.py" \
  --policy "$root/integration/yaml_libyaml/policy.json" \
  --boundary "$root/integration/yaml_libyaml/boundary.json" \
  --source "$yaml_src/src/api.c" \
  --out-dir "$yaml_generated" \
  --namespace "interspec::yaml_libyaml_generated"

python3 - "$yaml_generated/api.c" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
needle = '#include "yaml_private.h"\n'
assert needle in text
text = text.replace(needle, needle + '#include <stdint.h>\n#include "interspec_yaml_u_policy.h"\n', 1)
alloc = 'value_copy = YAML_MALLOC(length+1);'
assert text.count(alloc) >= 2
replacement = '''INTERSPEC_SITE_SCALAR_VALUE_BEGIN();
    value_copy = (yaml_char_t *)(uintptr_t)
        INTERSPEC_SITE_ALLOC((uint32_t)(length + 1));
    INTERSPEC_SITE_SCALAR_VALUE_END();'''
path.write_text(text.replace(alloc, replacement, 1))
PY

cp "$yaml_generated/api.c" "$yaml_src/src/api.c"
cp "$yaml_generated/interspec_u_policy.h" "$work/c_src/interspec_yaml_u_policy.h"
cp "$yaml_generated/interspec_t_policy.h" "$work/test/interspec_yaml_t_policy.h"
cp "$root/integration/yaml_libyaml/yaml_smoke.c" "$work/c_src/"
cp "$root/integration/yaml_libyaml/yaml_libyaml.inc.cpp" "$work/test/"
cp "$root/evaluation/p8_rlbox_bench.inc.cpp" "$work/test/"

python3 - "$work" <<'PY'
from pathlib import Path
import sys
repo = Path(sys.argv[1])
cmake = repo / "c_src/CMakeLists.txt"
text = cmake.read_text()
source_needle = "               ${CMAKE_SOURCE_DIR}/pcre-src/pcre_xclass.c)"
source_replacement = """               ${CMAKE_SOURCE_DIR}/pcre-src/pcre_xclass.c
               ${CMAKE_SOURCE_DIR}/yaml_smoke.c
               ${CMAKE_SOURCE_DIR}/libyaml-src/src/api.c
               ${CMAKE_SOURCE_DIR}/libyaml-src/src/reader.c
               ${CMAKE_SOURCE_DIR}/libyaml-src/src/scanner.c
               ${CMAKE_SOURCE_DIR}/libyaml-src/src/parser.c
               ${CMAKE_SOURCE_DIR}/libyaml-src/src/loader.c
               ${CMAKE_SOURCE_DIR}/libyaml-src/src/writer.c
               ${CMAKE_SOURCE_DIR}/libyaml-src/src/emitter.c
               ${CMAKE_SOURCE_DIR}/libyaml-src/src/dumper.c)"""
assert source_needle in text
text = text.replace(source_needle, source_replacement, 1)
include_needle = "  ${CMAKE_SOURCE_DIR}/pcre-src)"
include_replacement = """  ${CMAKE_SOURCE_DIR}/pcre-src
  ${CMAKE_SOURCE_DIR}/libyaml-src/include
  ${CMAKE_SOURCE_DIR}/libyaml-src/src)"""
assert include_needle in text
text = text.replace(include_needle, include_replacement, 1)
text += """
set_source_files_properties(
  ${CMAKE_SOURCE_DIR}/libyaml-src/src/api.c
  ${CMAKE_SOURCE_DIR}/libyaml-src/src/reader.c
  ${CMAKE_SOURCE_DIR}/libyaml-src/src/scanner.c
  ${CMAKE_SOURCE_DIR}/libyaml-src/src/parser.c
  ${CMAKE_SOURCE_DIR}/libyaml-src/src/loader.c
  ${CMAKE_SOURCE_DIR}/libyaml-src/src/writer.c
  ${CMAKE_SOURCE_DIR}/libyaml-src/src/emitter.c
  ${CMAKE_SOURCE_DIR}/libyaml-src/src/dumper.c
  PROPERTIES COMPILE_DEFINITIONS HAVE_CONFIG_H=1)
"""
cmake.write_text(text)
test = repo / "test/test_nacl_sandbox_glue.cpp"
t = test.read_text()
for inc in ('#include "yaml_libyaml.inc.cpp"\n', '#include "p8_rlbox_bench.inc.cpp"\n'):
    if inc not in t:
        t += "\n" + inc
test.write_text(t)
PY

cmake -S "$work" -B "$work/build" -DCMAKE_BUILD_TYPE=Release
rm -f "$work/build/nacl/glue_lib_nacl.nexe" \
      "$work/build/nacl_gcc/glue_lib_nacl.nexe"
cmake --build "$work/build" --target glue_lib_nacl --parallel 2
cmake --build "$work/build" --target test_rlbox_glue --parallel 2

"$work/build/test_rlbox_glue" "[typed_allocator]"
"$work/build/test_rlbox_glue" "[rsync_popt]"
"$work/build/test_rlbox_glue" "[memcached_bipbuffer]"
"$work/build/test_rlbox_glue" "[nginx_libpcre]"
"$work/build/test_rlbox_glue" "[yaml_libyaml]"

if [[ -n "${INTERSPEC_P8_RLBOX_RUNTIME:-}" ]]; then
  mkdir -p "$(dirname "$INTERSPEC_P8_RLBOX_RUNTIME")"
  INTERSPEC_P8_RLBOX_RUNTIME="$INTERSPEC_P8_RLBOX_RUNTIME" \
    "$work/build/test_rlbox_glue" "[p8_rlbox_bench]"
else
  "$work/build/test_rlbox_glue" "[p8_rlbox_bench]"
fi

if [[ -n "${INTERSPEC_P8_BOUNDARY_EVIDENCE:-}" ]]; then
  mkdir -p "$(dirname "$INTERSPEC_P8_BOUNDARY_EVIDENCE")"
  cat > "$INTERSPEC_P8_BOUNDARY_EVIDENCE" <<'EOF'
boundary,case,result
rsync/popt,wrong_type,pass
rsync/popt,untracked,pass
memcached/bipbuffer,wrong_type,pass
memcached/bipbuffer,untracked,pass
memcached/bipbuffer,out_of_bounds,pass
nginx/libpcre,wrong_type,pass
nginx/libpcre,untracked,pass
nginx/libpcre,out_of_bounds,pass
yaml/libyaml,wrong_type,pass
yaml/libyaml,untracked,pass
yaml/libyaml,out_of_bounds,pass
EOF
fi

echo "InterSpec P7c: yaml/libyaml structured scalar boundary passed in RLBox NaCl"
echo "InterSpec P7c: all synthetic, baseline, and three generalization boundaries passed together"
echo "InterSpec P8: matched RLBox domain-range benchmark passed"
