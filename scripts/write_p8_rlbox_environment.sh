#!/usr/bin/env bash
set -euo pipefail

out=${1:?output path required}
root=$(cd "$(dirname "$0")/.." && pwd)
commit=${GITHUB_SHA:-}
if [[ -z "$commit" ]]; then
  commit=$(git -C "$root" rev-parse HEAD 2>/dev/null || true)
fi
if [[ -z "$commit" ]]; then
  commit=unknown
fi
cpu=$(awk -F: '/^model name[[:space:]]*:/ {sub(/^[[:space:]]+/, "", $2); print $2; exit}' /proc/cpuinfo 2>/dev/null || true)
if [[ -z "$cpu" ]]; then
  cpu=unknown
fi
{
  echo "commit=$commit"
  echo "kernel=$(uname -srmo)"
  echo "cpu=$cpu"
  echo "boundary_iterations=${INTERSPEC_P8_BOUNDARY_ITERATIONS:-20000}"
  echo "boundary_repetitions=7"
  echo "application_repetitions=${INTERSPEC_P8_APP_REPETITIONS:-9}"
  echo "baseline=tracked_no_check"
  echo "extended=extended_sp3"
  echo "note=baseline retains typed allocation provenance and differs only in final T-side validation"
} > "$out"
