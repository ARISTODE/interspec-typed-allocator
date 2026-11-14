#!/usr/bin/env bash
# Tracker item C2: build a work directory for scripts/run_coverage_analysis.sh
# whose copies of the artifact's query pack and scripts have one named variant applied
# (evaluation/coverage/query_variants/). The databases and everything else are
# shared with the original work directory through symbolic links.
#
#   prepare_coverage_query_variant.sh VARIANT WORK VARIANT_WORK
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
variant=${1:?usage: prepare_coverage_query_variant.sh VARIANT WORK VARIANT_WORK}
work=$(cd "${2:?}" && pwd)
target=${3:?}
mkdir "$target" || { echo "variant work directory must not exist: $target" >&2; exit 2; }
target=$(cd "$target" && pwd)
ln -s "$work/db" "$target/db"
mkdir -p "$target/root/db" "$target/root/reports" "$target/root/coverage"
for entry in "$work/root"/*; do
  name=$(basename "$entry")
  case $name in
    db|reports|coverage|ql|scripts) ;;
    *) ln -s "$entry" "$target/root/$name" ;;
  esac
done
cp -r "$work/root/ql" "$target/root/ql"
cp -r "$work/root/scripts" "$target/root/scripts"
python3 "$repo/evaluation/coverage/query_variants/apply.py" "$variant" "$target/root"
echo "$variant" > "$target/query-variant.txt"
