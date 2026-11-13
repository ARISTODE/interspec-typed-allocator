#!/usr/bin/env bash
# Tracker item I1: rsync/popt with SP1, SP2 and full SP3 behind one switch each.
#
#   1. Test build (U may misbehave on request): the three switch tests.
#   2. The one build without test hooks: the complete rsync executable runs its
#      benign workload under each switch configuration and is compared with
#      native rsync built from the same revision.
#
# Every log, stdout, stderr and exit status is kept in the output directory,
# including those of a failing step. Nothing here is a timing measurement.
set -uo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:?usage: run_rsync_policy_switches.sh NEW_OUTPUT_DIR}
mkdir "$out" || { echo "output directory must not exist: $out" >&2; exit 2; }
out=$(cd "$out" && pwd)
base=${TMPDIR:-/tmp}
status=0

step() {  # step NAME COMMAND...: run, keep the log, record the exit status
  local name=$1; shift
  "$@" > "$out/$name.log" 2>&1
  local code=$?
  echo "$name exit=$code" | tee -a "$out/steps.txt"
  [[ $code == 0 ]] || status=1
  return $code
}

includes() {  # include flags for a work directory
  local work=$1
  printf '%s\n' -I"$work/include" -I"$work/build/_deps/rlbox-src/code/include" \
    -I"$work/build/_deps/wasm2c_compiler-src/wasm2c" \
    -I"$work/build/_deps/wasm2c_compiler-src/third_party/simde" \
    -I"$work/build/wasm_imported" -I"$root/include" \
    -I"$work/interspec-popt-generated" -I"$work/rsync-src/popt"
}

# 1. Switch tests on the test build.
test_tmp="$base/interspec-policy-switch-test"
mkdir -p "$test_tmp"
test_work="$test_tmp/interspec-rlbox-wasm2c"
if step build-test env TMPDIR="$test_tmp" INTERSPEC_FAULT_TESTS=1 \
     bash "$root/scripts/run_rlbox_wasm2c_poc.sh"; then
  module=$(find "$test_work/build" -name libglue_lib_imported.a -print -quit)
  mapfile -t inc < <(includes "$test_work")
  if step build-driver g++ -std=c++17 -O2 \
       "$root/integration/rsync_popt/policy_switch_test.cpp" \
       "$test_work/p9b_wasm_bridge.o" "${inc[@]}" "$module" \
       -pthread -ldl -lrt -lm -o "$test_work/policy-switch-test"; then
    step switch-tests python3 "$root/tools/run_policy_switch_tests.py" \
      --boundary rsync_popt --driver "$test_work/policy-switch-test" \
      --out "$out/switch-tests"
  fi
fi

# 2. Benign run of the complete rsync executable from the build without hooks.
release_tmp="$base/interspec-policy-switch-release"
mkdir -p "$release_tmp"
release_work="$release_tmp/interspec-rlbox-wasm2c"
if step build-release env TMPDIR="$release_tmp" \
     bash "$root/scripts/run_rlbox_wasm2c_poc.sh"; then
  if grep -q 'interspec_poc_set_flags\|interspec_test_set_fault' \
       "$release_work/build/wasm_imported/glue_lib_wasm2c.h"; then
    echo "release module unexpectedly exports test hooks" | tee -a "$out/steps.txt"
    status=1
  elif [[ -x "$test_work/rsync-native" ]]; then
    step benign python3 "$root/tools/test_rsync_policy_switches.py" \
      --rsync "$release_work/rsync-src/rsync" --native "$test_work/rsync-native" \
      --out "$out/benign"
  else
    echo "benign skipped: native reference missing" | tee -a "$out/steps.txt"
    status=1
  fi
fi

git -C "$root" rev-parse HEAD > "$out/source-commit.txt" 2>/dev/null || true
git -C "$root" status --porcelain > "$out/source-status.txt" 2>/dev/null || true
echo "overall exit=$status" | tee -a "$out/steps.txt"
exit $status
