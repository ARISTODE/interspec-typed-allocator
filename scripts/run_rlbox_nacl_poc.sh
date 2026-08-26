#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-rlbox-nacl
rm -rf "$work"

git clone -q https://github.com/PLSysSec/rlbox_nacl_sandbox.git "$work"
git -C "$work" checkout -q 0dd15342c86c0625c7c2ed7762a13feb524252d7

# The upstream .gclient still uses the SSH URL for the public compiler repo.
sed -i 's#git@github.com:PLSysSec/nacl_sandbox_compiler.git#https://github.com/PLSysSec/nacl_sandbox_compiler.git#' \
  "$work/nacl_rlbox/.gclient"
"$work/nacl_rlbox/call_gclient_sync.sh"
git -C "$work/nacl_rlbox/native_client" checkout -q \
  f274515ab22441ea6b4e937e519ace851fac308f

# P3: apply the versioned InterSpec backend to the pinned upstream revisions.
python3 "$root/backends/rlbox_nacl/apply_backend.py" --root "$work"

generated="$work/interspec-generated"
python3 "$root/tools/generate_policy.py" \
  --policy "$root/policy/poc_policy.json" \
  --source "$root/poc/typed_poc_untrusted.c" \
  --out-dir "$generated"

cp "$generated/typed_poc_untrusted.c" "$work/c_src/"
cp "$generated/interspec_u_policy.h" "$work/c_src/"
cp "$generated/interspec_t_policy.h" "$work/test/"
cp "$root/poc/typed_poc.inc.cpp" "$work/test/"
mkdir -p "$work/test/interspec"
cp "$root/include/interspec/runtime.h" "$work/test/interspec/"

# These edits are PoC test-harness glue only; the security backend is packaged
# independently under backends/rlbox_nacl/.
python3 - "$work" <<'PY'
from pathlib import Path
import sys

repo = Path(sys.argv[1])


def replace(path, old, new):
    text = path.read_text()
    assert old in text, f"patch context not found in {path}"
    path.write_text(text.replace(old, new, 1))


root_cmake = repo / "CMakeLists.txt"
replace(
    root_cmake,
    "FetchContent_Declare(\n  rlbox\n  GIT_REPOSITORY https://github.com/PLSysSec/rlbox_api_cpp17.git)",
    "FetchContent_Declare(\n  rlbox\n  GIT_REPOSITORY https://github.com/PLSysSec/rlbox.git\n  GIT_TAG b0157dc84f86ffbe4549e32ed5cbdfad79c17f43)")
replace(
    root_cmake,
    'add_subdirectory("${catch2_SOURCE_DIR}")',
    'add_subdirectory("${catch2_SOURCE_DIR}" "${catch2_BINARY_DIR}")')

cmake = repo / "c_src/CMakeLists.txt"
replace(
    cmake,
    "${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c)",
    "${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c\n"
    "               ${CMAKE_SOURCE_DIR}/typed_poc_untrusted.c)")

test = repo / "test/test_nacl_sandbox_glue.cpp"
include = '#include "typed_poc.inc.cpp"\n'
text = test.read_text()
if include not in text:
    test.write_text(text + "\n" + include)
PY

cmake -S "$work" -B "$work/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/build" --target glue_lib_nacl --parallel 2
cmake --build "$work/build" --target test_rlbox_glue --parallel 2
"$work/build/test_rlbox_glue" "[typed_allocator]"
