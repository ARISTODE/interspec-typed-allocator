#!/usr/bin/env bash
# Build step of scripts/run_ucl_port.sh (tracker item I11). A separate script,
# run with errexit, so that any failing command fails the build.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${1:?usage: build_ucl_port.sh WORK_DIR}
mkdir -p "$work"
source "$root/scripts/port_common.sh"
port_deps
port_source libucl
ucl="$work/src-libucl" generated="$work/generated" dir="$root/integration/ucl_libucl"
python3 "$root/tools/generate_wasm_boundary_policy.py" \
  --policy "$dir/policy.json" --boundary "$dir/boundary.json" \
  --source "$dir/ucl_u.c" --out-dir "$generated" \
  --namespace 'interspec::ucl_libucl_generated' --site-id-base 0x00500000
cp "$generated/interspec_u_policy.h" "$generated/interspec_ucl_u_policy.h"
cp "$generated/interspec_t_policy.h" "$generated/interspec_ucl_t_policy.h"
sources=()
for stem in util parser emitter emitter_streamline emitter_utils hash schema msgpack sexp; do
  sources+=("$ucl/src/ucl_$stem.c")
done
flags=(-D_GNU_SOURCE -D_WASI_EMULATED_MMAN -DHAVE_ATOMIC_BUILTINS=1
             -I"$ucl/include" -I"$ucl/src" -I"$ucl/uthash" -I"$ucl/klib" -I"$generated"
             -include "$dir/ucl_wasi_compat.h")
port_module ordinary - -- "${flags[@]}" -DINTERSPEC_TRACKING=0 \
  "${sources[@]}" "$dir/ucl_u.c" -lwasi-emulated-mman
port_module typed "$generated/interspec_wasm_imports.c" -- "${flags[@]}" \
  -DINTERSPEC_TRACKING=1 "${sources[@]}" "$dir/ucl_u.c" -lwasi-emulated-mman
port_module fault "$generated/interspec_wasm_imports.c" -- "${flags[@]}" \
  -DINTERSPEC_TRACKING=1 -DINTERSPEC_FAULT_TESTS=1 "${sources[@]}" "$dir/ucl_u.c" \
  -lwasi-emulated-mman
if grep -q 'interspecWasm' "$work/ordinary/glue_lib_wasm2c.h"; then
  echo 'RLBox-only module unexpectedly imports typed allocation' >&2; exit 1
fi
if grep -q 'interspec_ucl_fault\|interspec_ucl_poc' "$work/typed/glue_lib_wasm2c.h"; then
  echo 'Release module unexpectedly contains test hooks' >&2; exit 1
fi
mkdir -p "$work/bin" "$work/native"
objects=()
for source in "${sources[@]}"; do
  cc -O2 -D_GNU_SOURCE -I"$ucl/include" -I"$ucl/src" -I"$ucl/uthash" -I"$ucl/klib" \
    -c "$source" -o "$work/native/$(basename "${source%.c}").o"
  objects+=("$work/native/$(basename "${source%.c}").o")
done
g++ -std=c++17 -O2 -I"$ucl/include" "$dir/ucl_native_bench.cpp" "${objects[@]}" \
  -lm -o "$work/bin/ucl-native"
port_host "$work/bin/ucl-rlbox-only" ordinary 0 0 -- "$dir/ucl_app_bench.cpp"
port_host "$work/bin/ucl-tracked-no-check" typed 1 0 -- -I"$generated" "$dir/ucl_app_bench.cpp"
port_host "$work/bin/ucl-interspec" typed 1 1 -- -I"$generated" "$dir/ucl_app_bench.cpp"
port_host "$work/bin/ucl-interspec-fault" fault 1 1 -- -I"$generated" \
  -DINTERSPEC_FAULT_TESTS=1 "$dir/ucl_app_bench.cpp"
(cd "$work/bin" && sha256sum ucl-*) > "$work/binaries.sha256"
echo "libucl $(git -C "$ucl" rev-parse HEAD)" > "$work/source-revisions.txt"
