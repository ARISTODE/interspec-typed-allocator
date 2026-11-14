#!/usr/bin/env bash
# Tracker item I9: memcached/hash. Two cuts are built and tested:
#   - the hash function alone, as the interspec-artifact isolates it (SP2 is
#     the only policy with a field): steps switch-tests and benign;
#   - the hash function and memcached's hash table in U (JH decision of
#     2026-11-14), with SP1, SP2 and SP3 behind one switch each: steps assoc-*.
#
#   1. Build the hash function natively and as Wasm modules (with and without
#      the test hook), and the bench programs.
#   2. Switch test on the test build, where U misbehaves on request.
#   3. Benign run: every isolated variant must print the same result fields as
#      the native build on the cases in evaluation/parity/hash.
#
# Every log, stdout, stderr and exit status is kept in the output directory,
# including those of a failing step. Nothing here is a timing measurement.
set -uo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:?usage: run_hash_port.sh NEW_OUTPUT_DIR}
mkdir "$out" || { echo "output directory must not exist: $out" >&2; exit 2; }
out=$(cd "$out" && pwd)
work=${INTERSPEC_HASH_WORK:-${TMPDIR:-/tmp}/interspec-hash-port}
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

if step build bash "$root/scripts/build_hash_port.sh" "$work"; then
  cp "$work/binaries.sha256" "$work/source-revisions.txt" "$out/"
  step switch-tests python3 "$root/tools/run_policy_switch_tests.py" \
    --boundary memcached_hash --driver "$work/bin/hash-interspec-fault" \
    --out "$out/switch-tests"
  step benign python3 "$root/tools/run_port_parity.py" --boundary memcached_hash \
    --corpus "$root/evaluation/parity/hash" --bin "$work/bin" --out "$out/benign"
  # The hash table in U (JH decision of 2026-11-14).
  step assoc-switch-tests python3 "$root/tools/run_policy_switch_tests.py" \
    --boundary memcached_assoc --driver "$work/bin/assoc-interspec-fault" \
    --out "$out/assoc-switch-tests"
  step assoc-handles-rlbox-only python3 "$root/tools/run_policy_switch_tests.py" \
    --boundary memcached_assoc_rlbox_only --driver "$work/bin/assoc-rlbox-only-fault" \
    --out "$out/assoc-handles-rlbox-only"
  step assoc-benign python3 "$root/tools/run_port_parity.py" --boundary memcached_assoc \
    --corpus "$root/evaluation/parity/assoc" --bin "$work/bin" --out "$out/assoc-benign"
fi

git -C "$root" rev-parse HEAD > "$out/source-commit.txt" 2>/dev/null || true
git -C "$root" status --porcelain > "$out/source-status.txt" 2>/dev/null || true
echo "overall exit=$status" | tee -a "$out/steps.txt"
exit $status
