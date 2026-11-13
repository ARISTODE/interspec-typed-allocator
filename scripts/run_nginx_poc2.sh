#!/usr/bin/env bash
# Tracker item S3: PoC 2 (nginx/libpcre, PCRE 8.45) under RLBox-only and
# InterSpec. Builds the server variants with the untracked fault-test module
# added, then two copies of the policy-switch driver.
#
# Every log, stdout, stderr and exit status is kept in the output directory,
# including those of a failing step. Nothing here is a timing measurement.
set -uo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:?usage: run_nginx_poc2.sh NEW_OUTPUT_DIR}
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

build_driver() {  # build_driver NAME MODULE TRACKING CHECKS
  local wabt="$deps/build/_deps/wasm2c_compiler-src"
  g++ -std=c++17 -O2 -g \
    -DWASM_RT_USE_MMAP=1 -DWASM_RT_SKIP_SIGNAL_RECOVERY=1 \
    -DWASM_RT_NONCONFORMING_UNCHECKED_STACK_EXHAUSTION=1 \
    -DINTERSPEC_TRACKING="$3" -DINTERSPEC_CHECKS="$4" -DINTERSPEC_FAULT_TESTS=1 \
    -I"$deps/include" -I"$deps/build/_deps/rlbox-src/code/include" \
    -I"$wabt/wasm2c" -I"$wabt/third_party/simde" -I"$work/generated" \
    -I"$root/include" -I"$work/pcre" -I"$work/$2" \
    "$root/integration/nginx_server/policy_switch_test.cpp" \
    "$root/integration/nginx_server/bridge.cpp" "$work/$2/module.a" \
    -pthread -ldl -lrt -lm -o "$work/poc2-$1"
}

if step build env INTERSPEC_SECURITY_DELTA_BUILD=1 bash "$root/scripts/build_nginx_deployment.sh"; then
  if step build-driver-interspec build_driver interspec fault 1 1 &&
     step build-driver-rlbox build_driver rlbox fault-ordinary 0 0; then
    step poc2 python3 "$root/tools/run_poc2_nginx_pcre.py" \
      --interspec "$work/poc2-interspec" --rlbox "$work/poc2-rlbox" --out "$out/poc2"
  fi
fi

git -C "$root" rev-parse HEAD > "$out/source-commit.txt" 2>/dev/null || true
git -C "$root" status --porcelain > "$out/source-status.txt" 2>/dev/null || true
echo "overall exit=$status" | tee -a "$out/steps.txt"
exit $status
