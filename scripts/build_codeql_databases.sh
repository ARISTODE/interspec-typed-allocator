#!/usr/bin/env bash
# Tracker item C1: rebuild the CodeQL databases for the ten boundaries at the
# revisions in evaluation/coverage/pins.json.
#
#   build_codeql_databases.sh OUTPUT_DIR [DATABASE ...]
#
# Needs: CODEQL (path to the codeql executable of bundle v2.23.2) and
# INTERSPEC_ARTIFACT (a checkout of interspec-artifact at the pinned commit).
# The layout the artifact's configurations expect (benchmarks/, third_party/,
# workloads/, samples/, scripts/) is rebuilt under $COVERAGE_WORK/root.
# For each database the exact command, the source revisions, the full build
# log and a hash over the database files are written to OUTPUT_DIR/<name>/.
# A failed build is kept with its log; nothing is retried.
set -uo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
out=${1:?usage: build_codeql_databases.sh OUTPUT_DIR [DATABASE ...]}; shift
mkdir -p "$out"; out=$(cd "$out" && pwd)
pins="$repo/evaluation/coverage/pins.json"
codeql=${CODEQL:?set CODEQL to the codeql executable}
artifact=${INTERSPEC_ARTIFACT:?set INTERSPEC_ARTIFACT to an interspec-artifact checkout}
work=${COVERAGE_WORK:-${TMPDIR:-/tmp}/interspec-coverage}
root="$work/root"
status=0

want=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['analysis']['interspec_artifact_commit'])" "$pins")
[[ $(git -C "$artifact" rev-parse HEAD) == "$want" ]] || { echo "artifact checkout is not at $want" >&2; exit 2; }
"$codeql" version --format=terse > "$out/codeql-version.txt" 2>/dev/null
[[ $(cat "$out/codeql-version.txt") == 2.23.2 ]] || { echo "CodeQL 2.23.2 expected" >&2; exit 2; }

databases=("$@")  # taken before the loop below reuses the positional parameters
mkdir -p "$root" "$work/db"
for pair in "code/analysis/scripts scripts" "code/analysis/ql ql" "configs configs" \
            "code/workloads workloads" "code/generated_wrappers/samples samples"; do
  set -- $pair
  [[ -e "$root/$2" ]] || cp -a "$artifact/$1" "$root/$2"
done
mkdir -p "$root/coverage"
cp "$repo"/evaluation/coverage/build_*_for_codeql.sh "$root/coverage/"

fetch() {  # fetch SOURCE_NAME: clone the pinned revision into its path
  local name=$1 url revision path
  read -r url revision path < <(python3 -c "
import json,sys; s=json.load(open(sys.argv[1]))['sources'][sys.argv[2]]; print(s['url'], s['revision'], s['path'])" "$pins" "$name")
  if [[ ! -d "$root/$path/.git" ]]; then
    mkdir -p "$(dirname "$root/$path")"
    git clone -q "$url" "$root/$path" && git -C "$root/$path" checkout -q "$revision"
  fi
  [[ $(git -C "$root/$path" rev-parse HEAD) == "$revision" ]]
}

if [[ ${#databases[@]} == 0 ]]; then
  mapfile -t databases < <(python3 -c "import json,sys; print('\n'.join(json.load(open(sys.argv[1]))['databases']))" "$pins")
fi

for name in "${databases[@]}"; do
  record="$out/$name"
  mkdir "$record" || { echo "$name: record directory exists, not overwriting" | tee -a "$out/steps.txt"; status=1; continue; }
  command=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['databases'][sys.argv[2]]['command'])" "$pins" "$name")
  ok=1
  : > "$record/source-revisions.txt"
  for source in $(python3 -c "import json,sys; print(' '.join(json.load(open(sys.argv[1]))['databases'][sys.argv[2]]['sources']))" "$pins" "$name"); do
    if fetch "$source" >> "$record/fetch.log" 2>&1; then
      path=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['sources'][sys.argv[2]]['path'])" "$pins" "$source")
      echo "$source $path $(git -C "$root/$path" rev-parse HEAD)" >> "$record/source-revisions.txt"
    else
      ok=0
    fi
  done
  create=("$codeql" database create "$work/db/$name" --language=cpp --source-root="$root"
          --overwrite --threads=0 "--command=$command")
  printf '%q ' "${create[@]}" > "$record/command.txt"; echo >> "$record/command.txt"
  code=97
  if [[ $ok == 1 ]]; then
    (cd "$root" && "${create[@]}") > "$record/build.log" 2>&1
    code=$?
  fi
  if [[ $code == 0 ]]; then
    # Hash over every database file: sorted relative path and SHA-256.
    (cd "$work/db/$name" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$record/database-files.sha256"
    sha256sum "$record/database-files.sha256" | cut -d' ' -f1 > "$record/database-tree.sha256"
    du -sm "$work/db/$name" | cut -f1 > "$record/database-size-mb.txt"
    "$codeql" database print-baseline "$work/db/$name" > "$record/baseline.txt" 2>/dev/null || true
  fi
  echo "$name exit=$code" | tee -a "$out/steps.txt"
  [[ $code == 0 ]] || status=1
done
git -C "$repo" rev-parse HEAD > "$out/source-commit.txt"
echo "overall exit=$status" | tee -a "$out/steps.txt"
exit $status
