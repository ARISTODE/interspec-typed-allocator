#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/results/sp3-diagnostics"}
mkdir -p "$out"
out=$(cd "$out" && pwd)

# A fresh build ensures fault injection is present only in explicitly selected
# test artifacts, with no check bypass and the existing allocation policy.
INTERSPEC_DIAGNOSTICS=1 INTERSPEC_FAULT_TESTS=1 \
  bash "$root/scripts/run_rlbox_wasm2c_poc.sh" >"$out/build-wasm2c.log" 2>&1
cmake -S "$root" -B "$root/build-sp3" >"$out/build-core.log" 2>&1
cmake --build "$root/build-sp3" --parallel 2 >>"$out/build-core.log" 2>&1
ctest --test-dir "$root/build-sp3" --output-on-failure >"$out/core-tests.log" 2>&1
g++ -std=c++17 -O2 -pthread -DINTERSPEC_ENABLE_TRACE=1 -I"$root/include" \
  "$root/evaluation/security_eval.cpp" -o "$root/build-sp3/security-trace"
INTERSPEC_TRACE=1 "$root/build-sp3/security-trace" \
  >"$out/security.csv" 2>"$out/security-trace.stderr"
INTERSPEC_TRACE=1 "$root/build-sp3/diagnostics" \
  >"$out/metadata-dump.stdout" 2>"$out/metadata-dump.stderr"
status=0
python3 "$root/tools/run_sp3_experiments.py" --out "$out" >"$out/cases.jsonl" || status=$?
cat "$out/cases.jsonl"
exit "$status"
