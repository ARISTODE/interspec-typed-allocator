#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 || (${1:-} != "" && ${1:-} != "--build-only") ]]; then
  echo "Usage: $0 [--build-only]" >&2
  exit 2
fi

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-policy
rm -rf "$work"
mkdir -p "$work/stub"

cat > "$work/stub/interspec_u_policy.h" <<'EOF'
#pragma once
#include <stdint.h>
#define INTERSPEC_TYPE_ID_OTHER UINT32_C(2)
/* Analysis compiles objects only: no NaCl syscall implementation is needed.
 * Keep this separate from malloc so the adversarial call does not become an
 * inferred allocation site. The real backend also uses a uint32_t size/result.
 */
extern uint32_t interspec_analysis_site_alloc(uint32_t size);
#define INTERSPEC_SITE_ALLOC(size) interspec_analysis_site_alloc((uint32_t)(size))
EOF

cat > "$work/build.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cc -Werror=implicit-function-declaration -I"$work/stub" -c "$root/poc/typed_poc_untrusted.c" -o "$work/u.o"
c++ -std=c++17 -c "$root/analysis/poc_trusted_uses.cpp" -o "$work/t.o"
EOF
chmod +x "$work/build.sh"

# Exercise the exact extraction build without requiring a CodeQL installation.
if [[ ${1:-} == "--build-only" ]]; then
  "$work/build.sh"
  exit 0
fi

codeql pack install "$root/analysis/ql"

codeql database create "$work/db" \
  --language=cpp \
  --source-root="$root" \
  --command="$work/build.sh"

codeql query run \
  --database="$work/db" \
  --output="$work/policy.bqrs" \
  "$root/analysis/ql/policy_inference.ql"

codeql bqrs decode \
  --format=csv \
  --output="$work/policy.csv" \
  -- "$work/policy.bqrs"

cat "$work/policy.csv"

python3 "$root/tools/codeql_policy_to_json.py" \
  --csv "$work/policy.csv" \
  --output "$work/poc_policy.json"

cat "$work/poc_policy.json"
diff -u "$root/policy/poc_policy.json" "$work/poc_policy.json"

echo "InterSpec policy inference: generated policy matches checked-in policy"
