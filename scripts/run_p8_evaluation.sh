#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/p8-results"}
build=${INTERSPEC_P8_BUILD_DIR:-"$root/build-p8"}
repetitions=${INTERSPEC_P8_REPETITIONS:-5}
iterations=${INTERSPEC_BENCH_ITERATIONS:-200000}

if (( repetitions < 3 )); then
  echo "P8 requires at least 3 runtime repetitions" >&2
  exit 2
fi

rm -rf "$build" "$out"
mkdir -p "$out/runtime-runs"

cmake -S "$root" -B "$build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$build" --parallel
ctest --test-dir "$build" --output-on-failure | tee "$out/ctest.txt"

"$build/p6_security_eval" | tee "$out/security.csv"

runtime_inputs=()
for ((i = 1; i <= repetitions; ++i)); do
  run="$out/runtime-runs/runtime-$i.csv"
  INTERSPEC_BENCH_ITERATIONS="$iterations" "$build/p6_runtime_bench" > "$run"
  runtime_inputs+=("$run")
done
python3 "$root/tools/p8_aggregate_runtime.py" \
  --output "$out/runtime.csv" \
  "${runtime_inputs[@]}"

python3 "$root/tools/p7c_report.py" --require-complete \
  > "$out/p7c-generalization.json"

boundary_evidence=""
if [[ "${INTERSPEC_P8_RUN_RLBOX:-0}" == "1" ]]; then
  boundary_evidence="$out/boundary-security-evidence.csv"
  bash "$root/scripts/run_rlbox_nacl_poc.sh" \
    > "$out/rlbox-base.log" 2>&1
  INTERSPEC_P8_BOUNDARY_EVIDENCE="$boundary_evidence" \
    bash "$root/scripts/run_yaml_libyaml_rlbox_extension.sh" \
    > "$out/rlbox-combined.log" 2>&1
elif [[ -n "${INTERSPEC_P8_BOUNDARY_EVIDENCE:-}" ]]; then
  boundary_evidence="$out/boundary-security-evidence.csv"
  cp "$INTERSPEC_P8_BOUNDARY_EVIDENCE" "$boundary_evidence"
fi

collector=(
  python3 "$root/tools/p8_collect.py"
  --security "$out/security.csv"
  --runtime "$out/runtime.csv"
  --out-dir "$out"
)
if [[ -n "$boundary_evidence" ]]; then
  collector+=(--boundary-security "$boundary_evidence")
fi
if [[ "${INTERSPEC_P8_REQUIRE_BOUNDARY_EVIDENCE:-0}" == "1" ]]; then
  if [[ -z "$boundary_evidence" ]]; then
    echo "P8 boundary evidence was required but not supplied/generated" >&2
    exit 3
  fi
  collector+=(--require-boundary-evidence)
fi
"${collector[@]}"

cpu_model=$(awk -F: '/model name/ {gsub(/^[ \t]+/, "", $2); print $2; exit}' /proc/cpuinfo 2>/dev/null || true)
mem_kb=$(awk '/MemTotal/ {print $2; exit}' /proc/meminfo 2>/dev/null || true)
{
  echo "commit=$(git -C "$root" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "compiler=$(${CXX:-c++} --version | head -n 1)"
  echo "cmake=$(cmake --version | head -n 1)"
  echo "python=$(python3 --version 2>&1)"
  echo "kernel=$(uname -srmo)"
  echo "os=$(grep '^PRETTY_NAME=' /etc/os-release 2>/dev/null | cut -d= -f2- | tr -d '"' || true)"
  echo "cpu_model=$cpu_model"
  echo "logical_cpus=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo unknown)"
  echo "memory_kb=${mem_kb:-unknown}"
  echo "iterations=$iterations"
  echo "runtime_repetitions=$repetitions"
  echo "boundary_evidence=$([[ -n "$boundary_evidence" ]] && echo rlbox_nacl || echo manifest_only)"
  echo "utc_generated=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$out/environment.txt"

echo "P8 paper evaluation results written to $out"
