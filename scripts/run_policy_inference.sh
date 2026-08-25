#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-policy
rm -rf "$work"
mkdir -p "$work/stub"

cat > "$work/stub/interspec_u_policy.h" <<'EOF'
#pragma once
#include <stdint.h>
#define INTERSPEC_TYPE_ID_OTHER UINT32_C(2)
EOF

codeql pack install "$root/analysis/ql"

codeql database create "$work/db" \
  --language=cpp \
  --source-root="$root" \
  --command="cc -I'$work/stub' -c '$root/poc/typed_poc_untrusted.c' -o '$work/u.o' && c++ -std=c++17 -c '$root/analysis/poc_trusted_uses.cpp' -o '$work/t.o'"

codeql query run \
  --database="$work/db" \
  --output="$work/policy.bqrs" \
  "$root/analysis/ql/policy_inference.ql"

codeql bqrs decode \
  --format=csv \
  --output="$work/policy.csv" \
  -- "$work/policy.bqrs"

python3 "$root/tools/codeql_policy_to_json.py" \
  --csv "$work/policy.csv" \
  --output "$work/poc_policy.json"

diff -u "$root/policy/poc_policy.json" "$work/poc_policy.json"

echo "InterSpec policy inference: generated policy matches checked-in policy"
