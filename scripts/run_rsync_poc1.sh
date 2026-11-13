#!/usr/bin/env bash
# Tracker item S2: PoC 1 (rsync/popt) under RLBox-only, domain-only SP3 and
# full SP3. Uses the rsync/popt comparator build of the security-delta study
# for the RLBox-only module and the policy-switch driver as the PoC program.
#
# Every log, stdout, stderr and exit status is kept in the output directory,
# including those of a failing step. Nothing here is a timing measurement.
set -uo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:?usage: run_rsync_poc1.sh NEW_OUTPUT_DIR}
mkdir "$out" || { echo "output directory must not exist: $out" >&2; exit 2; }
out=$(cd "$out" && pwd)
base=${TMPDIR:-/tmp}/interspec-rsync-poc1
mkdir -p "$base"
work="$base/interspec-rlbox-wasm2c"
status=0

step() {  # step NAME COMMAND...: run, keep the log, record the exit status
  local name=$1; shift
  "$@" > "$out/$name.log" 2>&1
  local code=$?
  echo "$name exit=$code" | tee -a "$out/steps.txt"
  [[ $code == 0 ]] || status=1
  return $code
}

build_driver() {  # build_driver VARIANT [extra compiler flags]
  local variant=$1; shift
  g++ -std=c++17 -O2 -DINTERSPEC_FAULT_TESTS=1 "$@" \
    "$root/integration/rsync_popt/policy_switch_test.cpp" "$work/p9b_wasm_bridge.cpp" \
    -I"$work/include" -I"$work/build/_deps/rlbox-src/code/include" \
    -I"$work/build/_deps/wasm2c_compiler-src/wasm2c" \
    -I"$work/build/_deps/wasm2c_compiler-src/third_party/simde" \
    -I"$work/build/wasm_imported" -I"$root/include" \
    -I"$work/interspec-popt-generated" -I"$work/rsync-src/popt" \
    "$work/rsync-$variant-fault-module.a" -pthread -ldl -lrt -lm \
    -o "$work/poc1-$variant"
}

if step build-modules env TMPDIR="$base" bash "$root/scripts/build_rsync_security_delta.sh"; then
  if step build-driver-extended build_driver extended &&
     step build-driver-rlbox build_driver rlbox -DINTERSPEC_RLBOX_SECURITY_COMPARATOR=1; then
    step poc1 python3 "$root/tools/run_poc1_rsync_popt.py" \
      --extended "$work/poc1-extended" --rlbox "$work/poc1-rlbox" --out "$out/poc1"
  fi
fi

git -C "$root" rev-parse HEAD > "$out/source-commit.txt" 2>/dev/null || true
git -C "$root" status --porcelain > "$out/source-status.txt" 2>/dev/null || true
echo "overall exit=$status" | tee -a "$out/steps.txt"
exit $status
