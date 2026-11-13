#!/usr/bin/env bash
# Build step of scripts/run_png_port.sh (tracker item I8). A separate script,
# run with errexit, so that any failing command fails the build.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${1:?usage: build_png_port.sh WORK_DIR}
mkdir -p "$work"
source "$root/scripts/port_common.sh"
port_deps
port_source libpng
port_source zlib
png="$work/src-libpng" zlib="$work/src-zlib" generated="$work/generated"
dir="$root/integration/magick_libpng"
python3 "$root/tools/generate_wasm_boundary_policy.py" \
  --policy "$dir/policy.json" --boundary "$dir/boundary.json" \
  --source "$dir/magick_png_shim.c" --out-dir "$generated" \
  --namespace 'interspec::magick_libpng_generated' --site-id-base 0x00700000
cp "$generated/interspec_u_policy.h" "$generated/interspec_png_u_policy.h"
cp "$generated/interspec_t_policy.h" "$generated/interspec_png_t_policy.h"
cmp "$dir/magick_png_shim.c" "$generated/magick_png_shim.c"  # no site is rewritten

sources=()
while read -r library path; do
  case $library in
    libpng) sources+=("$png/$path") ;;
    zlib) sources+=("$zlib/$path") ;;
  esac
done < <(grep -v '^#' "$dir/sources.txt")
[[ ${#sources[@]} == 25 ]] || { echo "unexpected source count ${#sources[@]}" >&2; exit 1; }
# config/pnglibconf.h (from the artifact build) includes pnglibconf.h.prebuilt,
# which upstream libpng keeps under scripts/.
flags=(-DPNG_NO_STDIO=1 -I"$dir/config" -I"$png/scripts" -I"$png" -I"$zlib" -I"$dir"
       -I"$generated")
port_module ordinary - -- "${flags[@]}" -DINTERSPEC_TRACKING=0 \
  "${sources[@]}" "$dir/magick_png_shim.c" "$dir/png_u.c"
port_module typed "$generated/interspec_wasm_imports.c" -- "${flags[@]}" \
  -DINTERSPEC_TRACKING=1 "${sources[@]}" "$dir/magick_png_shim.c" "$dir/png_u.c"
port_module fault "$generated/interspec_wasm_imports.c" -- "${flags[@]}" \
  -DINTERSPEC_TRACKING=1 -DINTERSPEC_FAULT_TESTS=1 \
  "${sources[@]}" "$dir/magick_png_shim.c" "$dir/png_u.c"
if grep -q 'interspecWasm' "$work/ordinary/glue_lib_wasm2c.h"; then
  echo 'RLBox-only module unexpectedly imports typed allocation' >&2; exit 1
fi
if grep -q 'interspec_png_fault\|interspec_png_poc' "$work/typed/glue_lib_wasm2c.h"; then
  echo 'Release module unexpectedly contains test hooks' >&2; exit 1
fi

mkdir -p "$work/bin" "$work/native"
objects=()
for source in "${sources[@]}" "$dir/magick_png_shim.c"; do
  object="$work/native/$(basename "${source%.c}").o"
  cc -O2 -DPNG_NO_STDIO=1 -DINTERSPEC_TRACKING=0 -I"$dir/config" -I"$png/scripts" \
    -I"$png" -I"$zlib" -I"$dir" -c "$source" -o "$object"
  objects+=("$object")
done
g++ -std=c++17 -O2 -I"$dir" "$dir/png_native_bench.cpp" "${objects[@]}" -lm \
  -o "$work/bin/png-native"
port_host "$work/bin/png-rlbox-only" ordinary 0 0 -- "$dir/png_app_bench.cpp"
port_host "$work/bin/png-tracked-no-check" typed 1 0 -- -I"$generated" "$dir/png_app_bench.cpp"
port_host "$work/bin/png-interspec" typed 1 1 -- -I"$generated" "$dir/png_app_bench.cpp"
port_host "$work/bin/png-interspec-fault" fault 1 1 -- -I"$generated" \
  -DINTERSPEC_FAULT_TESTS=1 "$dir/png_app_bench.cpp"
(cd "$work/bin" && sha256sum png-*) > "$work/binaries.sha256"
{ echo "libpng $(git -C "$png" rev-parse HEAD)"; echo "zlib $(git -C "$zlib" rev-parse HEAD)"; } \
  > "$work/source-revisions.txt"
(cd "$root/evaluation/parity/png" && sha256sum -c SHA256SUMS) > "$work/corpus-check.txt"
for name in $(cut -d' ' -f3 "$root/evaluation/parity/png/SHA256SUMS"); do
  cmp "$root/evaluation/parity/png/$name" "$png/contrib/pngsuite/$name"
done
