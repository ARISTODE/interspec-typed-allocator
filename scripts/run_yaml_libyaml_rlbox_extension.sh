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

# libyaml normally generates this four-definition header during configure.
cat > "$yaml_src/include/config.h" <<'EOF'
#define YAML_VERSION_MAJOR 0
#define YAML_VERSION_MINOR 2
#define YAML_VERSION_PATCH 5
#define YAML_VERSION_STRING "0.2.5"
EOF

yaml_generated="$work/interspec-yaml-generated"
rm -rf "$yaml_generated"
python3 "$root/tools/generate_boundary_policy.py" \
  --policy "$root/integration/yaml_libyaml/policy.json" \
  --boundary "$root/integration/yaml_libyaml/boundary.json" \
  --source "$yaml_src/src/api.c" \
  --out-dir "$yaml_generated" \
  --namespace "interspec::yaml_libyaml_generated"

# yaml_scalar_event_initialize() owns the scalar value stored in the structured
# event. Patch only that first YAML_MALLOC(length+1) site; a later identical
# allocation belongs to scalar document nodes and is intentionally left alone.
python3 - "$yaml_generated/api.c" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
include_needle = '#include "yaml_private.h"\n'
include_insert = (
    include_needle
    + '#include <stdint.h>\n'
    + '#include "interspec_yaml_u_policy.h"\n'
)
assert include_needle in text
text = text.replace(include_needle, include_insert, 1)

alloc_needle = 'value_copy = YAML_MALLOC(length+1);'
assert text.count(alloc_needle) >= 2
alloc_replacement = '''INTERSPEC_SITE_SCALAR_VALUE_BEGIN();
    value_copy = (yaml_char_t *)(uintptr_t)
        INTERSPEC_SITE_ALLOC((uint32_t)(length + 1));
    INTERSPEC_SITE_SCALAR_VALUE_END();'''
text = text.replace(alloc_needle, alloc_replacement, 1)
path.write_text(text)
PY

cp "$yaml_generated/api.c" "$yaml_src/src/api.c"
cp "$yaml_generated/interspec_u_policy.h" "$work/c_src/interspec_yaml_u_policy.h"
cp "$yaml_generated/interspec_t_policy.h" "$work/test/interspec_yaml_t_policy.h"
cp "$root/integration/yaml_libyaml/yaml_smoke.c" "$work/c_src/"
cp "$root/integration/yaml_libyaml/yaml_libyaml.inc.cpp" "$work/test/"

# Extend the already-built P7c NaCl module rather than rebuilding the complete
# pinned NaCl toolchain a second time. The rebuilt test binary still contains
# every prior boundary, so the final commands exercise all boundaries together.
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

props = """
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
if "libyaml-src/src/api.c\n  PROPERTIES COMPILE_DEFINITIONS HAVE_CONFIG_H=1" not in text:
    text += props
cmake.write_text(text)

test = repo / "test/test_nacl_sandbox_glue.cpp"
test_text = test.read_text()
include = '#include "yaml_libyaml.inc.cpp"\n'
if include not in test_text:
    test_text += "\n" + include
test.write_text(test_text)
PY

cmake -S "$work" -B "$work/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/build" --target glue_lib_nacl --parallel 2
cmake --build "$work/build" --target test_rlbox_glue --parallel 2

# Re-run all Extended-SP3 boundary tests from the final combined binary.
"$work/build/test_rlbox_glue" "[typed_allocator]"
"$work/build/test_rlbox_glue" "[rsync_popt]"
"$work/build/test_rlbox_glue" "[memcached_bipbuffer]"
"$work/build/test_rlbox_glue" "[nginx_libpcre]"
"$work/build/test_rlbox_glue" "[yaml_libyaml]"

echo "InterSpec P7c: yaml/libyaml structured scalar boundary passed in RLBox NaCl"
echo "InterSpec P7c: all synthetic, baseline, and three generalization boundaries passed together"
