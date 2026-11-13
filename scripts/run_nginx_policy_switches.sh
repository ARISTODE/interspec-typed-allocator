#!/usr/bin/env bash
# Tracker item I4: nginx/libpcre (PCRE 8.45) with SP1, SP2 and full SP3 behind
# one switch each.
#
#   1. Build the server variants (the one build is nginx-interspec).
#   2. Switch tests: a T driver over the server's bridge source and the
#      fault-test U module, where U misbehaves on request.
#   3. The repository's nginx deployment gate with all three policies on.
#
#   4. The 104-response parity set rebuilt from the Stage 13 description
#      (evaluation/parity/nginx), on the four release variants.
#
# Every log, stdout, stderr and exit status is kept in the output directory,
# including those of a failing step. Nothing here is a timing measurement.
set -uo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:?usage: run_nginx_policy_switches.sh NEW_OUTPUT_DIR}
mkdir "$out" || { echo "output directory must not exist: $out" >&2; exit 2; }
out=$(cd "$out" && pwd)
work=${INTERSPEC_NGINX_WORK:-${TMPDIR:-/tmp}/interspec-nginx-deployment}
deps=${INTERSPEC_WASM_DEPS:-$work/wasm-deps}
export INTERSPEC_NGINX_WORK="$work"
status=0

step() {  # step NAME COMMAND...: run, keep the log, record the exit status
  local name=$1; shift
  "$@" > "$out/$name.log" 2>&1
  local code=$?
  echo "$name exit=$code" | tee -a "$out/steps.txt"
  [[ $code == 0 ]] || status=1
  return $code
}

if step build bash "$root/scripts/build_nginx_deployment.sh"; then
  cp "$work/build-manifest.json" "$out/build-manifest.json" 2>/dev/null || true
  wabt="$deps/build/_deps/wasm2c_compiler-src"
  if step build-driver g++ -std=c++17 -O2 -g \
       -DWASM_RT_USE_MMAP=1 -DWASM_RT_SKIP_SIGNAL_RECOVERY=1 \
       -DWASM_RT_NONCONFORMING_UNCHECKED_STACK_EXHAUSTION=1 \
       -DINTERSPEC_TRACKING=1 -DINTERSPEC_CHECKS=1 -DINTERSPEC_FAULT_TESTS=1 \
       -I"$deps/include" -I"$deps/build/_deps/rlbox-src/code/include" \
       -I"$wabt/wasm2c" -I"$wabt/third_party/simde" -I"$work/generated" \
       -I"$root/include" -I"$work/pcre" -I"$work/fault" \
       "$root/integration/nginx_server/policy_switch_test.cpp" \
       "$root/integration/nginx_server/bridge.cpp" "$work/fault/module.a" \
       -pthread -ldl -lrt -lm -o "$work/policy-switch-test"; then
    step switch-tests python3 "$root/tools/run_policy_switch_tests.py" \
      --boundary nginx_pcre --driver "$work/policy-switch-test" \
      --out "$out/switch-tests"
  fi
  step gate env INTERSPEC_SP1=1 INTERSPEC_SP2=1 INTERSPEC_SP3=1 \
    python3 "$root/tools/test_nginx_deployment.py" --work "$work" --out "$out/gate" --workers 2
  step parity python3 "$root/tools/run_nginx_parity.py" --work "$work" \
    --corpus "$root/evaluation/parity/nginx" --out "$out/parity"
fi

git -C "$root" rev-parse HEAD > "$out/source-commit.txt" 2>/dev/null || true
git -C "$root" status --porcelain > "$out/source-status.txt" 2>/dev/null || true
echo "overall exit=$status" | tee -a "$out/steps.txt"
exit $status
