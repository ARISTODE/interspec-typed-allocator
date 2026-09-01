#!/usr/bin/env bash
set -euo pipefail

# Keep the large pinned RLBox/NaCl integration recipe in a mechanically stable
# implementation file. This front-end supplies source-project preparation that
# must happen immediately after an upstream checkout, before that implementation
# configures the combined NaCl build.
script_dir=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$script_dir/.." && pwd)
impl="$script_dir/run_rlbox_nacl_poc_impl.sh"
git_bin=$(type -P git)

git()
{
  "$git_bin" "$@"
  local status=$?
  if [[ $status -eq 0 && $# -ge 5 && "$1" == "-C" &&
        "$3" == "checkout" && "$4" == "-q" &&
        "$5" == "e67dabe61b327bd2d888954b0e74a7c9cfd0a195" &&
        "$2" == */c_src/pcre-src ]]; then
    local pcre_src="$2"
    local pcre_config="${TMPDIR:-/tmp}/interspec-pcre-config"
    rm -rf "$pcre_config"
    cmake -S "$pcre_src" -B "$pcre_config" \
      -DBUILD_SHARED_LIBS=OFF \
      -DPCRE_BUILD_PCRE8=ON \
      -DPCRE_BUILD_PCRE16=OFF \
      -DPCRE_BUILD_PCRE32=OFF \
      -DPCRE_BUILD_PCRECPP=OFF \
      -DPCRE_BUILD_PCREGREP=OFF \
      -DPCRE_BUILD_TESTS=OFF \
      -DPCRE_SUPPORT_JIT=OFF \
      -DPCRE_SUPPORT_UTF=OFF \
      -DPCRE_SUPPORT_UNICODE_PROPERTIES=OFF \
      -DPCRE_SHOW_REPORT=OFF >/dev/null
    test -s "$pcre_config/config.h"
    cp "$pcre_config/config.h" "$pcre_src/config.h"
  fi
  return $status
}

filtered_impl=$(mktemp "${TMPDIR:-/tmp}/interspec-rlbox-nacl-impl.XXXXXX")
trap 'rm -f "$filtered_impl"' EXIT
python3 - "$impl" "$filtered_impl" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text()
for filename in ("pcre_jit_compile.c", "pcre_version.c"):
    needle = f'    "               ${{CMAKE_SOURCE_DIR}}/pcre-src/{filename}\\n"\n'
    count = source.count(needle)
    if count != 1:
        raise SystemExit(
            f"expected exactly one PCRE {filename} source-list entry, found {count}"
        )
    source = source.replace(needle, "")
Path(sys.argv[2]).write_text(source)
PY

# Source rather than exec so the preparation hook and all pinned build variables
# remain visible below for P8/P9a application measurements.
source "$filtered_impl"

# Preserve the Extended-SP3 NaCl module before creating the P9a RLBox-only
# module. Each trusted rsync binary below is linked against an immutable module
# path so later rebuilds cannot silently change its measurement configuration.
extended_module="$work/glue_lib_nacl-extended-sp3.nexe"
cp "$work/build/nacl/glue_lib_nacl.nexe" "$extended_module"

compile_bridge()
{
  local source_file=$1
  local output_obj=$2
  local module_path=$3
  shift 3
  g++ -std=c++17 -O2 -c "$source_file" \
    -o "$output_obj" \
    "$@" \
    -DGLUE_LIB_NACL_PATH=\"$module_path\" \
    -DNACL_LIBC_PATH=\"$work/nacl_rlbox/native_client/scons-out/nacl_irt-x86-64/staging/irt_core.nexe\" \
    -I"$work/include" \
    -I"$work/build/_deps/rlbox-src/code/include" \
    -I"$work/nacl_rlbox/native_client/src/trusted/dyn_ldr" \
    -I"$root/include" \
    -I"$work/test" \
    -I"$rsync_src/popt"
}

link_rsync()
{
  local bridge_obj=$1
  local output_binary=$2
  rm -f "$rsync_src/rsync"
  make -C "$rsync_src" -j2 rsync \
    P4C_BRIDGE="$bridge_obj" \
    P4C_LIBS="$p4c_libs"
  cp "$rsync_src/rsync" "$output_binary"
}

# Re-link the normal security configuration against the preserved module.
extended_bridge_obj="$work/p9a_extended_bridge.o"
compile_bridge "$root/integration/rsync_popt/p4c_bridge.cpp" \
  "$extended_bridge_obj" "$extended_module"
extended_rsync="$work/rsync-extended-sp3"
link_rsync "$extended_bridge_obj" "$extended_rsync"

# P8 tracked-no-check baseline. Typed allocation/provenance remains active and
# only the final T-side acceptance check is bypassed.
tracked_bridge_obj="$work/p8_no_validation_bridge.o"
compile_bridge "$root/integration/rsync_popt/p4c_bridge.cpp" \
  "$tracked_bridge_obj" "$extended_module" \
  -DINTERSPEC_P8_MEASURE_NO_VALIDATION=1
tracked_rsync="$work/rsync-tracked-no-check"
link_rsync "$tracked_bridge_obj" "$tracked_rsync"

# P9a true RLBox-only runtime path for the rsync/popt integration. Build the
# same NaCl module with the pinned, uninstrumented popt.c and without the
# INTERSPEC_TYPED_POPT interposition. Other dormant test sources remain linked,
# but the popt workload executes ordinary U malloc/realloc/free and no typed
# allocation site callback.
extended_popt_snapshot="$work/p9a-extended-popt.c"
extended_cmake_snapshot="$work/p9a-extended-cmake.txt"
cp "$rsync_src/popt/popt.c" "$extended_popt_snapshot"
cp "$work/c_src/CMakeLists.txt" "$extended_cmake_snapshot"

"$git_bin" -C "$rsync_src" show \
  7c20b077c980036a19587701cec320cc88e42a4a:popt/popt.c \
  > "$rsync_src/popt/popt.c"
python3 - "$work/c_src/CMakeLists.txt" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
needle = "  INTERSPEC_TYPED_POPT=1\n"
count = text.count(needle)
if count != 1:
    raise SystemExit(f"expected one INTERSPEC_TYPED_POPT definition, found {count}")
path.write_text(text.replace(needle, "", 1))
PY

cmake -S "$work" -B "$work/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
rm -f "$work/build/nacl/glue_lib_nacl.nexe" \
      "$work/build/nacl_gcc/glue_lib_nacl.nexe"
cmake --build "$work/build" --target glue_lib_nacl --parallel 2
rlbox_only_module="$work/glue_lib_nacl-rlbox-only.nexe"
cp "$work/build/nacl/glue_lib_nacl.nexe" "$rlbox_only_module"

# Generate a trusted bridge variant that creates only RLBox. It does not reserve
# the typed arena, instantiate PolicyRuntime, register allocation callbacks, or
# perform the Extended-SP3 acceptance check. Input marshalling uses ordinary
# RLBox sandbox allocation.
rlbox_only_bridge_src="$work/p4c_bridge_rlbox_only.cpp"
python3 "$root/tools/build_p9a_rlbox_only_bridge.py" \
  --source "$root/integration/rsync_popt/p4c_bridge.cpp" \
  --output "$rlbox_only_bridge_src"
rlbox_only_bridge_obj="$work/p9a_rlbox_only_bridge.o"
compile_bridge "$rlbox_only_bridge_src" \
  "$rlbox_only_bridge_obj" "$rlbox_only_module" \
  -DINTERSPEC_P9A_RLBOX_ONLY=1
rlbox_only_rsync="$work/rsync-rlbox-only"
link_rsync "$rlbox_only_bridge_obj" "$rlbox_only_rsync"

# Restore the Extended-SP3 source/build configuration for the later P7c YAML
# extension. The saved module is also restored at the canonical path.
cp "$extended_popt_snapshot" "$rsync_src/popt/popt.c"
cp "$extended_cmake_snapshot" "$work/c_src/CMakeLists.txt"
cmake -S "$work" -B "$work/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
cp "$extended_module" "$work/build/nacl/glue_lib_nacl.nexe"
cp "$extended_rsync" "$rsync_src/rsync"

# Every variant must complete the exact valid workloads before timing. The
# rlbox_only and tracked_no_check variants are measurement baselines and are not
# used for adversarial correctness claims.
for binary in "$rlbox_only_rsync" "$tracked_rsync" "$extended_rsync"; do
  "$binary" --backup-dir="$p4c_backup" --max-size=1M --block-size=1024 --version >/dev/null
  "$binary" --dry-run -a "$p4c_data/src/" "$p4c_data/dst/" >/dev/null
done

# One three-way sample stream is the source of truth for P9a. P8's existing
# tracked-no-check/Extended-SP3 CSV is mechanically filtered from the same
# repetitions, so the older incremental-validation result remains comparable.
p9a_csv=/tmp/interspec-p9a-rsync-performance.csv
python3 - "$rlbox_only_rsync" "$tracked_rsync" "$extended_rsync" \
  "$p4c_backup" "$p4c_data/src/" "$p4c_data/dst/" "$p9a_csv" <<'PY'
import csv
import os
import subprocess
import sys
import time

rlbox_only, tracked, extended, backup, src, dst, output = sys.argv[1:]
repetitions = int(os.environ.get(
    "INTERSPEC_P9A_APP_REPETITIONS",
    os.environ.get("INTERSPEC_P8_APP_REPETITIONS", "9"),
))
workloads = {
    "option_parse": [
        f"--backup-dir={backup}", "--max-size=1M", "--block-size=1024", "--version"
    ],
    "local_dry_run": ["--dry-run", "-a", src, dst],
}
variants = [
    ("rlbox_only", rlbox_only),
    ("tracked_no_check", tracked),
    ("extended_sp3", extended),
]
orders = [
    variants,
    [variants[1], variants[2], variants[0]],
    [variants[2], variants[0], variants[1]],
    list(reversed(variants)),
    [variants[1], variants[0], variants[2]],
    [variants[0], variants[2], variants[1]],
]
rows = []
for workload, args in workloads.items():
    for rep in range(repetitions):
        for mode, binary in orders[rep % len(orders)]:
            start = time.perf_counter_ns()
            subprocess.run([binary, *args], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elapsed = time.perf_counter_ns() - start
            rows.append((workload, mode, rep, elapsed))
with open(output, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["workload", "mode", "repetition", "total_ns"])
    writer.writerows(rows)
PY

app_csv=/tmp/interspec-p8-rsync-performance.csv
python3 - "$p9a_csv" "$app_csv" <<'PY'
import csv
import sys

source, output = sys.argv[1:]
with open(source, newline="") as f:
    rows = list(csv.DictReader(f))
with open(output, "w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["workload", "mode", "repetition", "total_ns"])
    writer.writeheader()
    for row in rows:
        if row["mode"] != "rlbox_only":
            writer.writerow(row)
PY

cat "$app_csv"
echo "InterSpec P8: paired full-rsync validation measurements written to $app_csv"
cat "$p9a_csv"
echo "InterSpec P9a: RLBox-only/tracking/full three-way measurements written to $p9a_csv"
