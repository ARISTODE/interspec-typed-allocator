#!/usr/bin/env bash
# Tracker item C2: run the interspec-artifact policy analysis on the rebuilt
# CodeQL databases (scripts/build_codeql_databases.sh must have run first).
#
#   run_coverage_analysis.sh OUTPUT_DIR BENCHMARK[:DATABASE] ...
#
# BENCHMARK is the artifact's benchmark id (its configuration); DATABASE is the
# database name when it differs (memcached_hash:memcached). Reports, the full
# log and the exit status of each benchmark are kept. Nothing is retried.
set -uo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
out=${1:?usage: run_coverage_analysis.sh OUTPUT_DIR BENCHMARK[:DATABASE] ...}; shift
mkdir -p "$out"; out=$(cd "$out" && pwd)
codeql=${CODEQL:?set CODEQL to the codeql executable}
work=${COVERAGE_WORK:-${TMPDIR:-/tmp}/interspec-coverage}
root="$work/root"
threads=${COVERAGE_THREADS:-0}
status=0
mkdir -p "$root/db" "$root/reports"

for item in "$@"; do
  benchmark=${item%%:*}
  database=${item#*:}
  record="$out/$benchmark"
  mkdir "$record" || { echo "$benchmark: record directory exists, not overwriting" | tee -a "$out/steps.txt"; status=1; continue; }
  ln -sfn "$work/db/$database" "$root/db/$database"
  rm -rf "$root/reports/$benchmark"
  command=(python3 scripts/run_slot_policy_analysis.py --database "db/$database"
           --benchmark "$benchmark" --output-dir "reports/$benchmark"
           --split-pointer-query --threads "$threads" --codeql "$codeql")
  # A configuration written for the rebuilt databases replaces the artifact's.
  if [[ -f "$repo/evaluation/coverage/configs/$benchmark.json" ]]; then
    mkdir -p "$root/coverage/configs"
    cp "$repo/evaluation/coverage/configs/$benchmark.json" "$root/coverage/configs/"
    cp "$repo/evaluation/coverage/configs/$benchmark.json" "$record/manifest.json"
    command+=(--manifest "coverage/configs/$benchmark.json")
  fi
  printf '%q ' "${command[@]}" > "$record/command.txt"; echo >> "$record/command.txt"
  (cd "$root" && "${command[@]}") 2>&1 | grep -v 'JAVA_TOOL_OPTIONS' > "$record/analysis.log"
  code=${PIPESTATUS[0]}
  cp "$root/reports/$benchmark"/*.csv "$record/" 2>/dev/null
  echo "$benchmark database=$database exit=$code" | tee -a "$out/steps.txt"
  [[ $code == 0 ]] || status=1
done
git -C "$repo" rev-parse HEAD > "$out/source-commit.txt"
echo "overall exit=$status" | tee -a "$out/steps.txt"
exit $status
