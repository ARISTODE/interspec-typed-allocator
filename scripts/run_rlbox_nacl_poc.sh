#!/usr/bin/env bash
set -euo pipefail

# Keep the large pinned RLBox/NaCl integration recipe in a mechanically stable
# implementation file. This front-end supplies source-project preparation that
# must happen immediately after an upstream checkout, before that implementation
# configures the combined NaCl build.
script_dir=$(cd "$(dirname "$0")" && pwd)
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
# remain visible below for P8's paired application measurement.
source "$filtered_impl"

# P8 application-level validation benchmark. This is deliberately a
# tracked-no-check baseline, not an RLBox-only baseline: typed allocation,
# provenance, sandboxing, marshalling, and the exact NaCl module stay identical.
# Only Engine::copy_checked() is compiled in measurement-only bypass mode.
baseline_bridge_obj="$work/p8_no_validation_bridge.o"
g++ -std=c++17 -O2 -c "$root/integration/rsync_popt/p4c_bridge.cpp" \
  -o "$baseline_bridge_obj" \
  -DINTERSPEC_P8_MEASURE_NO_VALIDATION=1 \
  -DGLUE_LIB_NACL_PATH=\"$work/build/nacl/glue_lib_nacl.nexe\" \
  -DNACL_LIBC_PATH=\"$work/nacl_rlbox/native_client/scons-out/nacl_irt-x86-64/staging/irt_core.nexe\" \
  -I"$work/include" \
  -I"$work/build/_deps/rlbox-src/code/include" \
  -I"$work/nacl_rlbox/native_client/src/trusted/dyn_ldr" \
  -I"$root/include" \
  -I"$work/test" \
  -I"$rsync_src/popt"

extended_rsync="$work/rsync-extended-sp3"
baseline_rsync="$work/rsync-tracked-no-check"
cp "$rsync_src/rsync" "$extended_rsync"
rm -f "$rsync_src/rsync"
make -C "$rsync_src" -j2 rsync \
  P4C_BRIDGE="$baseline_bridge_obj" \
  P4C_LIBS="$p4c_libs"
cp "$rsync_src/rsync" "$baseline_rsync"
cp "$extended_rsync" "$rsync_src/rsync"

# Both variants must still complete the exact valid acceptance workloads before
# timing. The baseline is measurement-only and is never used for attack tests.
"$baseline_rsync" --backup-dir="$p4c_backup" --max-size=1M --block-size=1024 --version >/dev/null
"$baseline_rsync" --dry-run -a "$p4c_data/src/" "$p4c_data/dst/" >/dev/null
"$extended_rsync" --backup-dir="$p4c_backup" --max-size=1M --block-size=1024 --version >/dev/null
"$extended_rsync" --dry-run -a "$p4c_data/src/" "$p4c_data/dst/" >/dev/null

app_csv=/tmp/interspec-p8-rsync-performance.csv
python3 - "$baseline_rsync" "$extended_rsync" "$p4c_backup" \
  "$p4c_data/src/" "$p4c_data/dst/" "$app_csv" <<'PY'
import csv
import os
import subprocess
import sys
import time

baseline, extended, backup, src, dst, output = sys.argv[1:]
repetitions = int(os.environ.get("INTERSPEC_P8_APP_REPETITIONS", "9"))
workloads = {
    "option_parse": [
        f"--backup-dir={backup}", "--max-size=1M", "--block-size=1024", "--version"
    ],
    "local_dry_run": ["--dry-run", "-a", src, dst],
}
variants = [("tracked_no_check", baseline), ("extended_sp3", extended)]
rows = []
for workload, args in workloads.items():
    for rep in range(repetitions):
        order = variants if rep % 2 == 0 else list(reversed(variants))
        for mode, binary in order:
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
cat "$app_csv"
echo "InterSpec P8: paired full-rsync validation measurements written to $app_csv"
