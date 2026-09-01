#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-rlbox-wasm2c
rm -rf "$work"

git clone -q https://github.com/PLSysSec/rlbox_wasm2c_sandbox.git "$work"
git -C "$work" checkout -q c4f18c48cea47421617f72ba5edc95c68aa85671
python3 "$root/backends/rlbox_wasm2c/apply_backend.py" --root "$work"

rsync_src="$work/rsync-src"
git clone -q https://github.com/RsyncProject/rsync.git "$rsync_src"
git -C "$rsync_src" checkout -q 7c20b077c980036a19587701cec320cc88e42a4a

popt_generated="$work/interspec-popt-generated"
python3 "$root/tools/generate_wasm_boundary_policy.py" \
  --policy "$root/integration/rsync_popt/policy.json" \
  --boundary "$root/integration/rsync_popt/boundary.json" \
  --source "$rsync_src/popt/popt.c" \
  --out-dir "$popt_generated" \
  --namespace "interspec::rsync_popt_generated"

# Compile a private copy of bundled popt into the Wasm module.
popt_wasm="$work/c_src/rsync-popt"
cp -R "$rsync_src/popt" "$popt_wasm"
cp "$popt_generated/popt.c" "$popt_wasm/popt.c"
cp "$popt_generated/interspec_u_policy.h" "$popt_wasm/interspec_popt_u_policy.h"
cp "$root/integration/rsync_popt/popt_typed_shim_wasm.c" "$work/c_src/"
cp "$root/integration/rsync_popt/p4c_bridge_untrusted.c" "$work/c_src/"
cp "$root/integration/rsync_popt/popt_help_stub.c" "$work/c_src/"
cp "$popt_generated/interspec_wasm_imports.c" "$work/src/"

python3 - "$popt_wasm/popt.c" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
needle = '#include "system.h"\n'
insert = needle + '#include <stdint.h>\n#include "interspec_popt_u_policy.h"\n'
assert needle in text
path.write_text(text.replace(needle, insert, 1))
PY

python3 - "$popt_wasm/system.h" <<'PY'
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

# Teach the upstream wasm2c test project to compile the real popt boundary into
# the Wasm module and to link the trusted import wrappers into the host runtime.
python3 - "$work/CMakeLists.txt" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
old = 'set(C_SOURCE_FILES "${CMAKE_SOURCE_DIR}/c_src/wasm2c_sandbox_wrapper.c")'
new = '''set(C_SOURCE_FILES
    "${CMAKE_SOURCE_DIR}/c_src/wasm2c_sandbox_wrapper.c"
    "${CMAKE_SOURCE_DIR}/c_src/rsync-popt/popt.c"
    "${CMAKE_SOURCE_DIR}/c_src/rsync-popt/poptconfig.c"
    "${CMAKE_SOURCE_DIR}/c_src/rsync-popt/poptparse.c"
    "${CMAKE_SOURCE_DIR}/c_src/rsync-popt/poptint.c"
    "${CMAKE_SOURCE_DIR}/c_src/popt_typed_shim_wasm.c"
    "${CMAKE_SOURCE_DIR}/c_src/p4c_bridge_untrusted.c"
    "${CMAKE_SOURCE_DIR}/c_src/popt_help_stub.c")'''
assert old in text
text = text.replace(old, new, 1)
source = '${CMAKE_SOURCE_DIR}/c_src/wasm2c_sandbox_wrapper.c\n                            ${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c'
replacement = '${C_SOURCE_FILES}\n                            ${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c'
assert text.count(source) == 2
text = text.replace(source, replacement)
flag = '                            -O3\n'
extra = '''                            -O3
                            -I${CMAKE_SOURCE_DIR}/c_src
                            -I${CMAKE_SOURCE_DIR}/c_src/rsync-popt
                            -DHAVE_STPCPY=1
                            -DHAVE_STRERROR=1
                            -DINTERSPEC_TYPED_POPT=1
                            -DPOPT_SYSCONFDIR=\"/etc\"
                            -DPACKAGE=\"rsync\"
'''
assert text.count(flag) == 2
text = text.replace(flag, extra)
needle = 'set(WASM2C_RUNTIME_CODE ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-impl.c\n                        ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-mem-impl.c\n                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_minwasi.c\n                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_mem.c)'
replacement = 'set(WASM2C_RUNTIME_CODE ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-impl.c\n                        ${WASM2C_RUNTIME_SOURCE_DIR}/wasm-rt-mem-impl.c\n                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_minwasi.c\n                        ${CMAKE_SOURCE_DIR}/src/wasm2c_rt_mem.c\n                        ${CMAKE_SOURCE_DIR}/src/interspec_wasm_imports.c)'
assert needle in text
text = text.replace(needle, replacement, 1)
path.write_text(text)
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
  -I"$popt_generated"
  -I"$rsync_src/popt"
)
common_libs=("$wasm_lib" -pthread -ldl -lrt -lm)

# Security smoke: valid helper allocation, spatial overflow, ordinary untracked
# allocation, wrong-type poptContext, and stale context after free.
g++ -std=c++17 -O2 \
  "$root/integration/rsync_popt/p9b_wasm_smoke.cpp" \
  "${common_includes[@]}" "${common_libs[@]}" \
  -o "$work/p9b-wasm-smoke"
"$work/p9b-wasm-smoke"
echo "InterSpec P9b: wasm2c security smoke passed"

# Build the complete trusted rsync executable with the same boundary bridge used
# by P4c, transformed mechanically from NaCl to wasm2c.
wasm_bridge="$work/p9b_wasm_bridge.cpp"
python3 "$root/tools/build_p9b_wasm2c_bridge.py" \
  --source "$root/integration/rsync_popt/p4c_bridge.cpp" \
  --output "$wasm_bridge"
bridge_obj="$work/p9b_wasm_bridge.o"
g++ -std=c++17 -O2 -c "$wasm_bridge" -o "$bridge_obj" "${common_includes[@]}"

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

p4c_libs="$wasm_lib -lstdc++ -pthread -ldl -lrt -lm"
make -j2 rsync P4C_BRIDGE="$bridge_obj" P4C_LIBS="$p4c_libs"

backup="$work/p9b-backup"
data="$work/p9b-data"
mkdir -p "$backup" "$data/src" "$data/dst"
printf 'InterSpec P9b wasm2c\n' > "$data/src/input.txt"
"$rsync_src/rsync" --backup-dir="$backup" --max-size=1M --block-size=1024 --version >/dev/null
"$rsync_src/rsync" --dry-run -a "$data/src/" "$data/dst/" >/dev/null

echo "InterSpec P9b: complete rsync executable ran with popt inside RLBox wasm2c"
