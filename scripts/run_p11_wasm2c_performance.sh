#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/p11-wasm2c-results"}
rm -rf "$out"
mkdir -p "$out"
out=$(cd "$out" && pwd)

base_tmp=${TMPDIR:-/tmp}
p11_tmp="$base_tmp/interspec-p11-driver"
rm -rf "$p11_tmp"
mkdir -p "$p11_tmp"

prepare_log="$out/p9b-prepare.log"
if ! TMPDIR="$p11_tmp" "$root/scripts/run_rlbox_wasm2c_poc.sh" >"$prepare_log" 2>&1; then
  echo "P11: P9b wasm2c preparation failed" >&2
  tail -n 300 "$prepare_log" >&2
  exit 1
fi

work="$p11_tmp/interspec-rlbox-wasm2c"
rsync_src="$work/rsync-src"
popt_generated="$work/interspec-popt-generated"
test -d "$rsync_src"
test -d "$popt_generated"

typed_wasm_lib=$(find "$work/build" -name 'libglue_lib_imported.a' -print -quit)
test -n "$typed_wasm_lib"
typed_wasm_snapshot="$work/libglue_lib_imported-p11-typed.a"
cp "$typed_wasm_lib" "$typed_wasm_snapshot"

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

compile_bridge()
{
  local source_file=$1
  local output_obj=$2
  shift 2
  g++ -std=c++17 -O2 -c "$source_file" -o "$output_obj" \
    "${common_includes[@]}" "$@"
}

link_rsync()
{
  local bridge_obj=$1
  local wasm_lib=$2
  local output_binary=$3
  local libs="$wasm_lib -lstdc++ -pthread -ldl -lrt -lm"
  rm -f "$rsync_src/rsync"
  make -C "$rsync_src" -j2 rsync \
    P4C_BRIDGE="$bridge_obj" \
    P4C_LIBS="$libs" >/dev/null
  cp "$rsync_src/rsync" "$output_binary"
}

# Build the two typed variants from one identical Wasm module. The only
# difference is whether T executes the final Extended-SP3 acceptance check.
extended_bridge_obj="$work/p11-extended-bridge.o"
compile_bridge "$work/p9b_wasm_bridge.cpp" "$extended_bridge_obj"
extended_rsync="$work/rsync-p11-extended-sp3"
link_rsync "$extended_bridge_obj" "$typed_wasm_snapshot" "$extended_rsync"

tracked_bridge_obj="$work/p11-tracked-no-check-bridge.o"
compile_bridge "$work/p9b_wasm_bridge.cpp" "$tracked_bridge_obj" \
  -DINTERSPEC_P8_MEASURE_NO_VALIDATION=1
tracked_rsync="$work/rsync-p11-tracked-no-check"
link_rsync "$tracked_bridge_obj" "$typed_wasm_snapshot" "$tracked_rsync"

# Build the matched RLBox-only runtime-path module. The real bundled popt source
# is restored to the pinned upstream version, typed allocator interposition is
# disabled, and the bridge helper used for T->U strings becomes ordinary malloc.
rsync_revision=7c20b077c980036a19587701cec320cc88e42a4a
"$(type -P git)" -C "$rsync_src" show \
  "$rsync_revision:popt/popt.c" > "$work/c_src/rsync-popt/popt.c"
python3 - "$work/c_src/rsync-popt/popt.c" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
needle = '#include "system.h"\n'
insert = needle + '#include "p9b_wasi_compat.h"\n'
if text.count(needle) != 1:
    raise SystemExit("unexpected pinned popt system.h include count")
path.write_text(text.replace(needle, insert, 1))
PY

cat > "$work/c_src/popt_typed_shim_wasm.c" <<'EOF'
#include <stdlib.h>
#include <string.h>

/*
 * P11 RLBox-only bridge helper. This symbol is retained only because the
 * application marshalling shim calls it; it performs an ordinary sandbox
 * allocation and has no InterSpec import, type, SiteId, or lifetime metadata.
 */
char* interspec_typed_strdup(const char* src)
{
  if (!src) return NULL;
  const size_t size = strlen(src) + 1;
  char* dst = (char*)malloc(size);
  if (!dst) return NULL;
  memcpy(dst, src, size);
  return dst;
}
EOF

python3 - "$work/CMakeLists.txt" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
needle = '                            -DINTERSPEC_TYPED_POPT=1\n'
count = text.count(needle)
if count == 0:
    raise SystemExit("P11 could not find typed popt compile definitions")
path.write_text(text.replace(needle, ''))
PY

cmake -S "$work" -B "$work/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$work/build" --target glue_lib_imported --parallel 2 >/dev/null
baseline_wasm_lib=$(find "$work/build" -name 'libglue_lib_imported.a' -print -quit)
test -n "$baseline_wasm_lib"
baseline_wasm_snapshot="$work/libglue_lib_imported-p11-rlbox-only.a"
cp "$baseline_wasm_lib" "$baseline_wasm_snapshot"

baseline_bridge_src="$work/p11_wasm_rlbox_only_bridge.cpp"
python3 "$root/tools/build_p11_wasm2c_rlbox_only_bridge.py" \
  --source "$work/p9b_wasm_bridge.cpp" \
  --output "$baseline_bridge_src"

# Mechanical baseline guards: none of the active setup operations may survive
# in the trusted bridge, and pinned popt must no longer contain typed site calls.
for marker in reserve_typed_arena set_interspec_runtime register_wasm_allocation_policy; do
  if grep -q "$marker" "$baseline_bridge_src"; then
    echo "P11 baseline bridge unexpectedly contains $marker" >&2
    exit 1
  fi
done
if grep -q 'interspec_wasm_alloc_' "$work/c_src/rsync-popt/popt.c"; then
  echo "P11 RLBox-only popt source is still instrumented" >&2
  exit 1
fi
if grep -q 'INTERSPEC_TYPED_POPT=1' "$work/CMakeLists.txt"; then
  echo "P11 RLBox-only module still enables typed allocator interposition" >&2
  exit 1
fi

baseline_bridge_obj="$work/p11-rlbox-only-bridge.o"
compile_bridge "$baseline_bridge_src" "$baseline_bridge_obj" \
  -DINTERSPEC_P8_MEASURE_NO_VALIDATION=1
rlbox_only_rsync="$work/rsync-p11-rlbox-only"
link_rsync "$baseline_bridge_obj" "$baseline_wasm_snapshot" "$rlbox_only_rsync"

backup="$work/p11-backup"
data="$work/p11-data"
mkdir -p "$backup" "$data/src" "$data/dst"
printf 'InterSpec P11 wasm2c performance\n' > "$data/src/input.txt"

# Correctness gate before timing. Every performance configuration must execute
# the same valid complete-process workloads successfully.
for binary in "$rlbox_only_rsync" "$tracked_rsync" "$extended_rsync"; do
  "$binary" --backup-dir="$backup" --max-size=1M --block-size=1024 --version >/dev/null
  "$binary" --dry-run -a "$data/src/" "$data/dst/" >/dev/null
done

raw="$out/rsync-performance.csv"
python3 - "$rlbox_only_rsync" "$tracked_rsync" "$extended_rsync" \
  "$backup" "$data/src/" "$data/dst/" "$raw" <<'PY'
import csv
import os
import shutil
import subprocess
import sys
import time

rlbox_only, tracked, extended, backup, src, dst, output = sys.argv[1:]
repetitions = int(os.environ.get("INTERSPEC_P11_REPETITIONS", "15"))
warmups = int(os.environ.get("INTERSPEC_P11_WARMUPS", "2"))
if repetitions < 3:
    raise SystemExit("INTERSPEC_P11_REPETITIONS must be at least 3")
if warmups < 0:
    raise SystemExit("INTERSPEC_P11_WARMUPS must be non-negative")

cpu = os.environ.get("INTERSPEC_P11_CPU", "").strip()
prefix = []
if cpu:
    taskset = shutil.which("taskset")
    if not taskset:
        raise SystemExit("INTERSPEC_P11_CPU was set but taskset is unavailable")
    prefix = [taskset, "-c", cpu]

env = os.environ.copy()
env["LC_ALL"] = "C"
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

def run(binary, args):
    subprocess.run(prefix + [binary, *args], check=True, env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

for _, args in workloads.items():
    for _ in range(warmups):
        for _, binary in variants:
            run(binary, args)

rows = []
for workload, args in workloads.items():
    for rep in range(repetitions):
        for mode, binary in orders[rep % len(orders)]:
            begin = time.perf_counter_ns()
            run(binary, args)
            elapsed = time.perf_counter_ns() - begin
            rows.append((workload, mode, rep, elapsed))

with open(output, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["workload", "mode", "repetition", "total_ns"])
    writer.writerows(rows)
PY

summary="$out/rsync-performance-summary.csv"
python3 "$root/tools/summarize_p9a_application.py" \
  --input "$raw" \
  --output "$summary"

commit=${GITHUB_SHA:-}
if [[ -z "$commit" ]]; then
  commit=$(git -C "$root" rev-parse HEAD 2>/dev/null || true)
fi
[[ -n "$commit" ]] || commit=unknown
cpu_model=$(awk -F: '/^model name[[:space:]]*:/ {sub(/^[[:space:]]+/, "", $2); print $2; exit}' /proc/cpuinfo 2>/dev/null || true)
[[ -n "$cpu_model" ]] || cpu_model=unknown
governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || true)
[[ -n "$governor" ]] || governor=unknown
if [[ -r /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then
  turbo="intel_pstate_no_turbo=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo)"
elif [[ -r /sys/devices/system/cpu/cpufreq/boost ]]; then
  turbo="cpufreq_boost=$(cat /sys/devices/system/cpu/cpufreq/boost)"
else
  turbo=unknown
fi
hosted_ci=${GITHUB_ACTIONS:-false}
{
  echo "commit=$commit"
  echo "kernel=$(uname -srmo)"
  echo "cpu=$cpu_model"
  echo "logical_cpus=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo unknown)"
  echo "governor=$governor"
  echo "turbo=$turbo"
  echo "cpu_affinity=${INTERSPEC_P11_CPU:-unrestricted}"
  echo "repetitions=${INTERSPEC_P11_REPETITIONS:-15}"
  echo "warmups=${INTERSPEC_P11_WARMUPS:-2}"
  echo "hosted_ci=$hosted_ci"
  echo "measurement=complete process wall time via time.perf_counter_ns"
  echo "rlbox_baseline=rlbox_only"
  echo "tracking_configuration=tracked_no_check"
  echo "security_configuration=extended_sp3"
  echo "rlbox_wasm2c_revision=c4f18c48cea47421617f72ba5edc95c68aa85671"
  echo "rsync_revision=$rsync_revision"
  echo "note=hosted CI timings are reference measurements; publication values require a controlled host"
} > "$out/environment.txt"

python3 - "$summary" "$out/environment.txt" "$commit" "$out/P11_RESULTS.md" <<'PY'
import csv
import sys
from pathlib import Path

summary, environment, commit, output = sys.argv[1:]
with open(summary, newline="") as f:
    rows = list(csv.DictReader(f))

def num(v):
    return f"{float(v):.3f}"

def pct(v):
    return f"{float(v):.1f}%"

lines = [
    "# P11 RLBox wasm2c Performance Results",
    "",
    "This file is mechanically rendered from the P11 three-way complete-rsync measurement stream.",
    "Hosted CI values are reproducibility references only; use the same driver on controlled hardware for publication numbers.",
    "",
    "Reference commit:", "", "```text", commit, "```", "",
    "Environment:", "", "```text", Path(environment).read_text().strip(), "```", "",
    "| Workload | RLBox only median (ms) | Tracking/no-check median (ms) | Extended SP3 median (ms) | Tracking/provenance overhead | Validation overhead | Total Extended-SP3 overhead |",
    "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
]
for row in rows:
    lines.append(
        f"| {row['workload']} | {num(row['rlbox_median_ms'])} | "
        f"{num(row['tracked_median_ms'])} | {num(row['extended_median_ms'])} | "
        f"{pct(row['tracking_overhead_median_pct'])} | "
        f"{pct(row['validation_overhead_median_pct'])} | "
        f"{pct(row['total_overhead_median_pct'])} |"
    )
lines += [
    "",
    "Tracking/provenance is computed per repetition as `tracked_no_check / rlbox_only - 1`; validation as `extended_sp3 / tracked_no_check - 1`; total overhead as `extended_sp3 / rlbox_only - 1`.",
    "The component percentages are not additive because their denominators differ.",
    "",
]
Path(output).write_text("\n".join(lines))
PY

cat > "$out/README.txt" <<'EOF'
P11 RLBox wasm2c performance artifact

rsync-performance.csv
  Raw paired three-way complete-process samples.

rsync-performance-summary.csv
  Median/mean timing and paired tracking, validation, and total overhead.

P11_RESULTS.md
  Mechanically rendered table from the raw/summary data.

environment.txt
  Host, CPU, frequency-policy, affinity, repetition, and revision metadata.

p9b-prepare.log
  Complete preparation log for the typed wasm2c implementation.

The RLBox-only path uses pinned uninstrumented bundled popt, ordinary sandbox
allocation, no typed arena, no PolicyRuntime initialization, no allocation-site
callback installation, and no final Extended-SP3 pointer check. Dormant backend
support code may remain linked, matching the P9a runtime-path-baseline model.

Hosted CI timing is a reproducibility reference, not a publication result.
EOF

cat "$summary"
echo "InterSpec P11: wasm2c three-way performance results written to $out"
