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

# P3/P7a: apply the versioned InterSpec backend to the pinned upstream revisions.
python3 "$root/backends/rlbox_nacl/apply_backend.py" --root "$work"

# Shared U primitive used by every precise, source-derived allocation site.
cp "$root/backends/rlbox_nacl/interspec_site_allocator.h" "$work/c_src/"
cp "$root/integration/interspec_site_allocator_state.c" "$work/c_src/"

# Synthetic mechanism PoC. P7b uses the boundary generator even when no
# boundary-helper sites are present, so the same generated policy interface is
# exercised by synthetic and real integrations.
generated="$work/interspec-generated"
python3 "$root/tools/generate_boundary_policy.py" \
  --policy "$root/policy/poc_policy.json" \
  --source "$root/poc/typed_poc_untrusted.c" \
  --out-dir "$generated"

cp "$generated/typed_poc_untrusted.c" "$work/c_src/"
cp "$generated/interspec_u_policy.h" "$work/c_src/"
cp "$generated/interspec_t_policy.h" "$work/test/"
cp "$root/poc/typed_poc.inc.cpp" "$work/test/"
mkdir -p "$work/test/interspec"
cp "$root/include/interspec/runtime.h" "$work/test/interspec/"
cp "$root/include/interspec/policy_runtime.h" "$work/test/interspec/"

# P4/P7b: compile and execute the real bundled popt implementation used by
# rsync. CodeQL-derived sites and boundary-helper sites are emitted through one
# generated policy interface.
rsync_src="$work/c_src/rsync-src"
git clone -q https://github.com/RsyncProject/rsync.git "$rsync_src"
git -C "$rsync_src" checkout -q 7c20b077c980036a19587701cec320cc88e42a4a

popt_generated="$work/interspec-popt-generated"
python3 "$root/tools/generate_boundary_policy.py" \
  --policy "$root/integration/rsync_popt/policy.json" \
  --boundary "$root/integration/rsync_popt/boundary.json" \
  --source "$rsync_src/popt/popt.c" \
  --out-dir "$popt_generated" \
  --namespace "interspec::rsync_popt_generated"

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
)
assert needle in text
popt.write_text(text.replace(needle, insert, 1))
PY

cp "$popt_generated/popt.c" "$rsync_src/popt/popt.c"
cp "$popt_generated/interspec_u_policy.h" "$work/c_src/interspec_popt_u_policy.h"
cp "$popt_generated/interspec_t_policy.h" "$work/test/interspec_popt_t_policy.h"
cp "$root/integration/rsync_popt/popt_typed_shim.c" "$work/c_src/"
cp "$root/integration/rsync_popt/popt_smoke.c" "$work/c_src/"
cp "$root/integration/rsync_popt/popt_help_stub.c" "$work/c_src/"
cp "$root/integration/rsync_popt/p4c_bridge_untrusted.c" "$work/c_src/"
cp "$root/integration/rsync_popt/rsync_popt.inc.cpp" "$work/test/"

# Real popt can resize and destroy allocations after the selected typed malloc
# sites execute. Route those lifetime operations through the trusted runtime
# when the pointer belongs to the InterSpec arena, and retain normal libc
# behavior for all ordinary popt allocations.
python3 - "$rsync_src/popt/system.h" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
needle = '#endif  /* defined(HAVE_MCHECK_H) && defined(__GNUC__) */\n'
insert = needle + r'''

#ifdef INTERSPEC_TYPED_POPT
void interspec_typed_free(void *ptr);
void * interspec_typed_realloc(void *ptr, size_t size);
char * interspec_typed_strdup(const char *str);
#undef free
#undef realloc
#undef xrealloc
#undef strdup
#undef xstrdup
#define free(_ptr) interspec_typed_free((_ptr))
#define realloc(_ptr, _size) interspec_typed_realloc((_ptr), (_size))
#define xrealloc(_ptr, _size) interspec_typed_realloc((_ptr), (_size))
#define strdup(_str) interspec_typed_strdup((_str))
#define xstrdup(_str) interspec_typed_strdup((_str))
#endif
'''
assert needle in text
path.write_text(text.replace(needle, insert, 1))
PY

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
    "               ${CMAKE_SOURCE_DIR}/interspec_site_allocator_state.c\n"
    "               ${CMAKE_SOURCE_DIR}/typed_poc_untrusted.c\n"
    "               ${CMAKE_SOURCE_DIR}/popt_typed_shim.c\n"
    "               ${CMAKE_SOURCE_DIR}/popt_smoke.c\n"
    "               ${CMAKE_SOURCE_DIR}/popt_help_stub.c\n"
    "               ${CMAKE_SOURCE_DIR}/p4c_bridge_untrusted.c\n"
    "               ${CMAKE_SOURCE_DIR}/rsync-src/popt/popt.c\n"
    "               ${CMAKE_SOURCE_DIR}/rsync-src/popt/poptconfig.c\n"
    "               ${CMAKE_SOURCE_DIR}/rsync-src/popt/poptparse.c\n"
    "               ${CMAKE_SOURCE_DIR}/rsync-src/popt/poptint.c)")
replace(
    cmake,
    "target_include_directories(glue_lib_nacl.nexe PUBLIC ${modnacl_SOURCE_DIR})",
    "target_include_directories(glue_lib_nacl.nexe PUBLIC\n"
    "  ${modnacl_SOURCE_DIR}\n"
    "  ${CMAKE_SOURCE_DIR}\n"
    "  ${CMAKE_SOURCE_DIR}/rsync-src/popt)\n"
    "target_compile_definitions(glue_lib_nacl.nexe PRIVATE\n"
    "  HAVE_STPCPY=1\n"
    "  HAVE_STRERROR=1\n"
    "  INTERSPEC_TYPED_POPT=1\n"
    "  POPT_SYSCONFDIR=\"/etc\"\n"
    "  PACKAGE=\"rsync\")")

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

# P4c: build the complete trusted rsync executable while interposing its popt
# API with an RLBox bridge. The host uses system libpopt only for standalone
# helpers such as poptDupArgv()/poptStrerror(); every context-dependent parser
# operation is supplied by p4c_bridge.cpp and executes the real bundled popt in
# the NaCl module built above.
cd "$rsync_src"
./configure \
  --disable-md2man \
  --disable-xxhash \
  --disable-zstd \
  --disable-lz4 \
  --disable-openssl \
  --disable-idn \
  --disable-roll-simd \
  --disable-roll-asm \
  --disable-md5-asm

bridge_obj="$work/p4c_bridge.o"
g++ -std=c++17 -O2 -c "$root/integration/rsync_popt/p4c_bridge.cpp" \
  -o "$bridge_obj" \
  -DGLUE_LIB_NACL_PATH=\"$work/build/nacl/glue_lib_nacl.nexe\" \
  -DNACL_LIBC_PATH=\"$work/nacl_rlbox/native_client/scons-out/nacl_irt-x86-64/staging/irt_core.nexe\" \
  -I"$work/include" \
  -I"$work/build/_deps/rlbox-src/code/include" \
  -I"$work/nacl_rlbox/native_client/src/trusted/dyn_ldr" \
  -I"$root/include" \
  -I"$work/test" \
  -I"$rsync_src/popt"

python3 - "$rsync_src/Makefile" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
old = '$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJS) $(LIBS)'
new = '$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJS) $(P4C_BRIDGE) $(LIBS) $(P4C_LIBS)'
assert old in text
path.write_text(text.replace(old, new, 1))
PY

nacl_libdir="$work/nacl_rlbox/native_client/scons-out/opt-linux-x86-64/lib"
nacl_libs=(
  "$nacl_libdir/libdyn_ldr.a"
  "$nacl_libdir/libsel.a"
  "$nacl_libdir/libnacl_error_code.a"
  "$nacl_libdir/libenv_cleanser.a"
  "$nacl_libdir/libnrd_xfer.a"
  "$nacl_libdir/libnacl_perf_counter.a"
  "$nacl_libdir/libnacl_base.a"
  "$nacl_libdir/libimc.a"
  "$nacl_libdir/libnacl_fault_inject.a"
  "$nacl_libdir/libnacl_interval.a"
  "$nacl_libdir/libplatform_qual_lib.a"
  "$nacl_libdir/libvalidators.a"
  "$nacl_libdir/libdfa_validate_caller_x86_64.a"
  "$nacl_libdir/libcpu_features.a"
  "$nacl_libdir/libvalidation_cache.a"
  "$nacl_libdir/libplatform.a"
  "$nacl_libdir/libgio.a"
  "$nacl_libdir/libnccopy_x86_64.a"
)
p4c_libs="-Wl,--start-group ${nacl_libs[*]} -Wl,--end-group -lstdc++ -pthread -ldl -lrt"

make -j2 rsync P4C_BRIDGE="$bridge_obj" P4C_LIBS="$p4c_libs"

# Exercise a destination-backed string option and direct poptGetOptArg uses
# through the complete rsync main executable.
p4c_backup="$work/p4c-backup"
mkdir -p "$p4c_backup"
"$rsync_src/rsync" --backup-dir="$p4c_backup" --max-size=1M --block-size=1024 --version >/dev/null

# Exercise positional arguments and the normal local-transfer startup path.
p4c_data="$work/p4c-rsync-data"
mkdir -p "$p4c_data/src" "$p4c_data/dst"
printf 'InterSpec P4c\n' > "$p4c_data/src/input.txt"
"$rsync_src/rsync" --dry-run -a "$p4c_data/src/" "$p4c_data/dst/" >/dev/null

echo "InterSpec P4c: complete rsync executable ran with popt inside RLBox NaCl"
