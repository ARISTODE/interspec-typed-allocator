#!/usr/bin/env bash
# Fresh current-source profile. No retry or replacement of any existing output.
set -euo pipefail
if [[ $# != 2 ]]; then
  echo "usage: $0 OUTPUT_DIRECTORY CORRECTNESS_SUMMARY" >&2
  exit 2
fi
root=$(cd "$(dirname "$0")/.." && pwd)
out=$(realpath -m "$1")
gate=$(realpath "$2")
work=${INTERSPEC_MEMCACHED_WORK:-${TMPDIR:-/tmp}/interspec-memcached-deployment}
mkdir "$out"
python3 "$root/tools/profile_memcached_checks.py" prepare-current \
  --plan-directory "$out/frozen" --out "$out/raw" \
  --client-build-directory "$out/client-build" --work "$work" \
  --correctness-summary "$gate"
env -u INTERSPEC_MEMCACHED_WORK python3 "$root/tools/profile_memcached_checks.py" collect --plan "$out/frozen/plan.json"
python3 "$root/tools/verify_memcached_profile.py" --profile "$out/raw" --plan "$out/frozen/plan.json"
python3 "$root/tools/export_memcached_profile.py" --profile "$out/raw" \
  --plan "$out/frozen/plan.json" --output "$out/check-frequency.json"
