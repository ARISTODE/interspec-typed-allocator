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

# Synthetic mechanism PoC.
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

# P4: compile and execute the real bundled popt implementation used by rsync.
rsync_src="$work/c_src/rsync-src"
git clone -q https://github.com/RsyncProject/rsync.git "$rsync_src"
git -C "$rsync_src" checkout -q 7c20b077c980036a19587701cec320cc88e42a4a

popt_generated="$work/interspec-popt-generated"
python3 "$root/tools/generate_policy.py" \
  --policy "$root/integration/rsync_popt/policy.json" \
  --source "$rsync_src/popt/popt.c" \
  --out-dir "$popt_generated"

python3 - "$popt_generated" <<'PY'
from pathlib import Path
import sys

out = Path(sys.argv[1])
popt = out / "popt.c"
text = popt.read_text()
needle = '#include "system.h"\n'
insert = (
    '#include "system.h"\n'
    '#include <stdint.h>\n'
    '#include "interspec_popt_u_policy.h"\n'
    'extern uint32_t typed_alloc(uint32_t, uint32_t);\n'
)
assert needle in text
popt.write_text(text.replace(needle, insert, 1))

t_header = out / "interspec_t_policy.h"
text = t_header.read_text().replace(
    "namespace interspec::generated", "namespace interspec::rsync_popt_generated")
t_header.write_text(text)
PY

cp "$popt_generated/popt.c" "$rsync_src/popt/popt.c"
cp "$popt_generated/interspec_u_policy.h" "$work/c_src/interspec_popt_u_policy.h"
cp "$popt_generated/interspec_t_policy.h" "$work/test/interspec_popt_t_policy.h"
cp "$root/integration/rsync_popt/popt_typed_shim.c" "$work/c_src/"
cp "$root/integration/rsync_popt/popt_smoke.c" "$work/c_src/"
cp "$root/integration/rsync_popt/rsync_popt.inc.cpp" "$work/test/"

# These edits are PoC/test-harness glue only; the security backend is packaged
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
    "               ${CMAKE_SOURCE_DIR}/typed_poc_untrusted.c\n"
    "               ${CMAKE_SOURCE_DIR}/popt_typed_shim.c\n"
    "               ${CMAKE_SOURCE_DIR}/popt_smoke.c\n"
    "               ${CMAKE_SOURCE_DIR}/rsync-src/popt/popt.c\n"
    "               ${CMAKE_SOURCE_DIR}/rsync-src/popt/poptconfig.c\n"
    "               ${CMAKE_SOURCE_DIR}/rsync-src/popt/popthelp.c\n"
    "               ${CMAKE_SOURCE_DIR}/rsync-src/popt/poptparse.c\n"
    "               ${CMAKE_SOURCE_DIR}/rsync-src/popt/poptint.c)")
replace(
    cmake,
    "target_include_directories(glue_lib_nacl.nexe PUBLIC ${modnacl_SOURCE_DIR})",
    "target_include_directories(glue_lib_nacl.nexe PUBLIC\n"
    "  ${modnacl_SOURCE_DIR}\n"
    "  ${CMAKE_SOURCE_DIR}\n"
    "  ${CMAKE_SOURCE_DIR}/rsync-src/popt)")

test = repo / "test/test_nacl_sandbox_glue.cpp"
text = test.read_text()
for include in ('#include "typed_poc.inc.cpp"\n', '#include "rsync_popt.inc.cpp"\n'):
    if include not in text:
        text += "\n" + include
test.write_text(text)
PY

cmake -S "$work" -B "$work/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/build" --target glue_lib_nacl --parallel 2
cmake --build "$work/build" --target test_rlbox_glue --parallel 2
"$work/build/test_rlbox_glue" "[typed_allocator]"
"$work/build/test_rlbox_glue" "[rsync_popt]"
