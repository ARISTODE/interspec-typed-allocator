#!/usr/bin/env bash
# Build step of scripts/run_zip_port.sh (tracker item I12). A separate script,
# run with errexit, so that any failing command fails the build.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${1:?usage: build_zip_port.sh WORK_DIR}
mkdir -p "$work"
source "$root/scripts/port_common.sh"
port_deps
port_source libzip
port_source zlib
zip="$work/src-libzip" zlib="$work/src-zlib" generated="$work/generated"
dir="$root/integration/zip_libzip"
mkdir -p "$generated" "$work/common"
(cd "$work/common" && cmake -DPROJECT_SOURCE_DIR="$zip" \
  -P "$zip/cmake/GenerateZipErrorStrings.cmake")

# The registry learns the name buffers at their allocation site in libzip:
# zip_string.c is instrumented by the generator (the malloc in
# _zip_string_new). The buffer of a converted name is allocated in
# zip_utf-8.c and is routed to a declared site. Both are released in
# _zip_string_free. Each replacement must match exactly once.
python3 "$root/tools/generate_wasm_boundary_policy.py" \
  --policy "$dir/policy.json" --boundary "$dir/boundary.json" \
  --source "$zip/lib/zip_string.c" --out-dir "$generated" \
  --namespace 'interspec::zip_libzip_generated' --site-id-base 0x00600000
cp "$generated/interspec_u_policy.h" "$generated/interspec_zip_u_policy.h"
cp "$generated/interspec_t_policy.h" "$generated/interspec_zip_t_policy.h"
python3 - "$generated/zip_string.c" "$zip/lib/zip_utf-8.c" "$generated/zip_utf-8.c" <<'PY'
import sys
from pathlib import Path
def replace_once(text, old, new):
    if text.count(old) != 1:
        sys.exit(f"expected exactly one occurrence of {old!r}")
    return text.replace(old, new)
string_c = Path(sys.argv[1])
text = string_c.read_text()
if "interspec_wasm_alloc_" not in text:
    sys.exit("zip_string.c was not instrumented")
text = replace_once(
    text, "    free(s->raw);\n    free(s->converted);\n",
    "    (void)interspec_wasm_release((uint32_t)(uintptr_t)s->raw);\n"
    "    if (s->converted)\n"
    "        (void)interspec_wasm_release((uint32_t)(uintptr_t)s->converted);\n")
string_c.write_text(text)
utf8 = Path(sys.argv[2]).read_text()
Path(sys.argv[3]).write_text(replace_once(
    utf8, "(utf8buf = (zip_uint8_t *)malloc(buflen))",
    "(utf8buf = (zip_uint8_t *)(uintptr_t)INTERSPEC_SITE_CONVERTED_NAME_ALLOC(buflen))"))
PY

plain=() tracked=()
while read -r library path; do
  case $library in
    zlib) plain+=("$zlib/$path"); tracked+=("$zlib/$path") ;;
    libzip)
      plain+=("$zip/$path")
      case $path in
        lib/zip_string.c|lib/zip_utf-8.c) tracked+=("$generated/$(basename "$path")") ;;
        *) tracked+=("$zip/$path") ;;
      esac ;;
  esac
done < <(grep -v '^#' "$dir/sources.txt")
plain+=("$work/common/zip_err_str.c"); tracked+=("$work/common/zip_err_str.c")
[[ ${#plain[@]} == 125 ]] || { echo "unexpected source count ${#plain[@]}" >&2; exit 1; }
flags=(-D_GNU_SOURCE -I"$dir/config" -I"$zip/lib" -I"$zlib" -I"$dir" -I"$generated"
       -include "$dir/zip_wasi_compat.h")
port_module ordinary - -- "${flags[@]}" -DINTERSPEC_TRACKING=0 \
  "${plain[@]}" "$dir/zip_shim.c" "$dir/zip_u.c"
port_module typed "$generated/interspec_wasm_imports.c" -- "${flags[@]}" \
  -DINTERSPEC_TRACKING=1 -include "$generated/interspec_zip_u_policy.h" \
  "${tracked[@]}" "$dir/zip_shim.c" "$dir/zip_u.c"
port_module fault "$generated/interspec_wasm_imports.c" -- "${flags[@]}" \
  -DINTERSPEC_TRACKING=1 -DINTERSPEC_FAULT_TESTS=1 \
  -include "$generated/interspec_zip_u_policy.h" \
  "${tracked[@]}" "$dir/zip_shim.c" "$dir/zip_u.c"
if grep -q 'interspecWasm' "$work/ordinary/glue_lib_wasm2c.h"; then
  echo 'RLBox-only module unexpectedly imports typed allocation' >&2; exit 1
fi
if grep -q 'interspec_zip_fault\|interspec_zip_poc' "$work/typed/glue_lib_wasm2c.h"; then
  echo 'Release module unexpectedly contains test hooks' >&2; exit 1
fi

mkdir -p "$work/bin" "$work/native"
objects=()
for source in "${plain[@]}"; do
  object="$work/native/$(basename "${source%.c}").o"
  cc -O2 -D_GNU_SOURCE -I"$dir/config" -I"$zip/lib" -I"$zlib" -c "$source" -o "$object"
  objects+=("$object")
done
g++ -std=c++17 -O2 -I"$dir/config" -I"$zip/lib" "$dir/zip_native_bench.cpp" \
  "${objects[@]}" -o "$work/bin/zip-native"
host=(-I"$dir/config" -I"$zip/lib")
port_host "$work/bin/zip-rlbox-only" ordinary 0 0 -- "${host[@]}" "$dir/zip_app_bench.cpp"
port_host "$work/bin/zip-tracked-no-check" typed 1 0 -- "${host[@]}" -I"$generated" \
  "$dir/zip_app_bench.cpp"
port_host "$work/bin/zip-interspec" typed 1 1 -- "${host[@]}" -I"$generated" \
  "$dir/zip_app_bench.cpp"
port_host "$work/bin/zip-interspec-fault" fault 1 1 -- "${host[@]}" -I"$generated" \
  -DINTERSPEC_FAULT_TESTS=1 "$dir/zip_app_bench.cpp"
(cd "$work/bin" && sha256sum zip-*) > "$work/binaries.sha256"
{ echo "libzip $(git -C "$zip" rev-parse HEAD)"; echo "zlib $(git -C "$zlib" rev-parse HEAD)"; } \
  > "$work/source-revisions.txt"
(cd "$root/evaluation/parity/zip" && sha256sum -c SHA256SUMS) > "$work/corpus-check.txt"
for name in $(cut -d' ' -f3 "$root/evaluation/parity/zip/SHA256SUMS"); do
  cmp "$root/evaluation/parity/zip/$name" "$zip/regress/$name"
done
