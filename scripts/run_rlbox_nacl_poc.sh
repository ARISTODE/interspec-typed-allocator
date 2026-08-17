#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-rlbox-nacl
rm -rf "$work"
mkdir -p "$work/nacl_rlbox"

git clone -q https://github.com/PLSysSec/rlbox_nacl_sandbox.git "$work/rlbox_nacl_sandbox"
git -C "$work/rlbox_nacl_sandbox" checkout -q 0dd15342c86c0625c7c2ed7762a13feb524252d7
git clone -q https://github.com/PLSysSec/nacl_sandbox_compiler.git "$work/nacl_rlbox/native_client"
git -C "$work/nacl_rlbox/native_client" checkout -q f274515ab22441ea6b4e937e519ace851fac308f

cp "$root/poc/typed_poc_untrusted.c" "$work/rlbox_nacl_sandbox/c_src/"
cp "$root/poc/typed_poc.inc.cpp" "$work/rlbox_nacl_sandbox/test/"
cp "$root/src/typed_arena.h" "$work/rlbox_nacl_sandbox/test/"

python3 - "$work/rlbox_nacl_sandbox" <<'PY'
from pathlib import Path
import sys

repo = Path(sys.argv[1])
root_cmake = repo / "CMakeLists.txt"
text = root_cmake.read_text()
text = text.replace(
    "FetchContent_Declare(\n  rlbox\n  GIT_REPOSITORY https://github.com/PLSysSec/rlbox_api_cpp17.git)",
    "FetchContent_Declare(\n  rlbox\n  GIT_REPOSITORY https://github.com/PLSysSec/rlbox.git\n  GIT_TAG b0157dc84f86ffbe4549e32ed5cbdfad79c17f43)")
text = text.replace(
    'add_subdirectory("${catch2_SOURCE_DIR}")',
    'add_subdirectory("${catch2_SOURCE_DIR}" "${catch2_BINARY_DIR}")')
root_cmake.write_text(text)

cmake = repo / "c_src/CMakeLists.txt"
text = cmake.read_text()
needle = "${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c)"
assert needle in text
cmake.write_text(text.replace(
    needle,
    "${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c\n"
    "               ${CMAKE_SOURCE_DIR}/typed_poc_untrusted.c)"))

test = repo / "test/test_nacl_sandbox_glue.cpp"
text = test.read_text()
include = '#include "typed_poc.inc.cpp"\n'
if include not in text:
    test.write_text(text + "\n" + include)
PY

cmake -S "$work/rlbox_nacl_sandbox" -B "$work/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/build" --target test_rlbox_glue --parallel 2
"$work/build/test_rlbox_glue" "[typed_allocator]"
