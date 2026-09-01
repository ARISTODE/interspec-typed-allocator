#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/p8-results"}
p6_out="$out/p6"

rm -rf "$out"
mkdir -p "$out"

# Reuse the P6 security/runtime benchmark implementation rather than creating a
# second benchmark path with subtly different semantics.
bash "$root/scripts/run_p6_evaluation.sh" "$p6_out"

python3 "$root/tools/p7c_report.py" \
  --output "$out/p7c-generalization.json" \
  --require-complete

python3 "$root/tools/build_p8_report.py" \
  --security-csv "$p6_out/security.csv" \
  --output-dir "$out" \
  --require-complete

{
  echo "commit=$(git -C "$root" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "compiler=$(${CXX:-c++} --version | head -n 1)"
  echo "cmake=$(cmake --version | head -n 1)"
  echo "kernel=$(uname -srmo)"
  if command -v lscpu >/dev/null 2>&1; then
    echo "cpu=$(lscpu | awk -F: '/Model name/ {gsub(/^[ \t]+/, "", $2); print $2; exit}')"
  else
    echo "cpu=unknown"
  fi
  echo "iterations=${INTERSPEC_BENCH_ITERATIONS:-200000}"
} > "$out/environment.txt"

cat > "$out/README.txt" <<'EOF'
P8 deterministic evidence:
  p8-deterministic.json
  p8-automation.csv
  p7c-generalization.json

P8 runtime evidence inherited from the common P6 benchmark path:
  p6/security.csv
  p6/runtime.csv
  p6/environment.txt

Hosted-runner timing is measurement evidence only, never a performance gate.
Final paper timings should be regenerated on controlled hardware using this same
output structure.
EOF

echo "P8 evaluation results written to $out"
