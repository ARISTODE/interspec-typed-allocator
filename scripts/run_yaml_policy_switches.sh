#!/usr/bin/env bash
# Tracker item I3: yaml/libyaml with SP2 and SP3 behind one switch each. There
# is no SP1 test at this boundary: T sends U only the document, which U has to
# read, so there is no field to withhold.
#
#   1. Build the bench programs (release builds and the fault-test build).
#   2. Switch tests on the fault-test build, where U misbehaves on request.
#   3. The rebuilt 48-run parity set on the builds without test hooks.
#
# Every log, stdout, stderr and exit status is kept in the output directory,
# including those of a failing step. Nothing here is a timing measurement.
set -uo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:?usage: run_yaml_policy_switches.sh NEW_OUTPUT_DIR}
mkdir "$out" || { echo "output directory must not exist: $out" >&2; exit 2; }
out=$(cd "$out" && pwd)
work="${TMPDIR:-/tmp}/interspec-yaml-libyaml"
corpus="$root/evaluation/parity/yaml"
status=0

step() {  # step NAME COMMAND...: run, keep the log, record the exit status
  local name=$1; shift
  "$@" > "$out/$name.log" 2>&1
  local code=$?
  echo "$name exit=$code" | tee -a "$out/steps.txt"
  [[ $code == 0 ]] || status=1
  return $code
}

# The evaluation script builds all programs; its own benchmark pass is skipped.
if step build env INTERSPEC_SECURITY_DELTA_ONLY=1 \
     bash "$root/scripts/run_yaml_libyaml_evaluation.sh" "$out/build-output"; then
  step switch-tests python3 "$root/tools/run_policy_switch_tests.py" \
    --boundary yaml_libyaml --driver "$work/yaml-typed-fault" \
    --document "$corpus/block_flow.yaml" --out "$out/switch-tests"
  step parity python3 "$root/tools/run_yaml_parity.py" \
    --native "$work/yaml-native-bench" --rlbox "$work/yaml-rlbox-bench" \
    --typed "$work/yaml-typed-bench" --corpus "$corpus" --out "$out/parity"
fi

git -C "$root" rev-parse HEAD > "$out/source-commit.txt" 2>/dev/null || true
git -C "$root" status --porcelain > "$out/source-status.txt" 2>/dev/null || true
echo "overall exit=$status" | tee -a "$out/steps.txt"
exit $status
