#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-rlbox-nacl
rm -rf "$work"
mkdir -p "$work/nacl_rlbox"

git clone --depth 1 https://github.com/PLSysSec/rlbox_nacl_sandbox.git "$work/rlbox_nacl_sandbox"
git clone --depth 1 https://github.com/PLSysSec/nacl_sandbox_compiler.git "$work/nacl_rlbox/native_client"

cp "$root/poc/typed_poc_untrusted.c" "$work/rlbox_nacl_sandbox/c_src/"
cp "$root/poc/typed_poc.inc.cpp" "$work/rlbox_nacl_sandbox/test/"
cp "$root/src/typed_arena.h" "$work/rlbox_nacl_sandbox/test/"

python3 - "$work/rlbox_nacl_sandbox" <<'PY'
from pathlib import Path
import sys

repo = Path(sys.argv[1])
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
