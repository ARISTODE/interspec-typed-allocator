#!/usr/bin/env bash
# Tracker item I12: zip/libzip with SP1, SP2 and SP3 (object registry) behind
# one switch each.
#
#   1. Build libzip and zlib at the pinned revisions natively and as Wasm modules
#      (RLBox-only, tracked, tracked with test hooks), and the bench programs.
#   2. Switch tests on the test build, where U misbehaves on request.
#   3. Benign run: every isolated variant must print the same result fields as
#      the native build on the cases in evaluation/parity/zip.
#
# Every log, stdout, stderr and exit status is kept in the output directory,
# including those of a failing step. Nothing here is a timing measurement.
set -uo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:?usage: run_zip_port.sh NEW_OUTPUT_DIR}
mkdir "$out" || { echo "output directory must not exist: $out" >&2; exit 2; }
out=$(cd "$out" && pwd)
work=${INTERSPEC_ZIP_WORK:-${TMPDIR:-/tmp}/interspec-zip-port}
mkdir -p "$work"
status=0

step() {  # step NAME COMMAND...: run, keep the log, record the exit status
  local name=$1; shift
  "$@" > "$out/$name.log" 2>&1
  local code=$?
  echo "$name exit=$code" | tee -a "$out/steps.txt"
  [[ $code == 0 ]] || status=1
  return $code
}

if step build bash "$root/scripts/build_zip_port.sh" "$work"; then
  cp "$work/binaries.sha256" "$work/source-revisions.txt" "$work/corpus-check.txt" "$out/"
  step switch-tests python3 "$root/tools/run_policy_switch_tests.py" \
    --boundary zip_libzip --driver "$work/bin/zip-interspec-fault" \
    --document "$root/evaluation/parity/zip/test.zip" --out "$out/switch-tests"
  step benign python3 "$root/tools/run_port_parity.py" --boundary zip_libzip \
    --corpus "$root/evaluation/parity/zip" --bin "$work/bin" --out "$out/benign"
fi

git -C "$root" rev-parse HEAD > "$out/source-commit.txt" 2>/dev/null || true
git -C "$root" status --porcelain > "$out/source-status.txt" 2>/dev/null || true
echo "overall exit=$status" | tee -a "$out/steps.txt"
exit $status
