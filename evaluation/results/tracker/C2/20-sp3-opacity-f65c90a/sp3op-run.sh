#!/usr/bin/env bash
# Run the pointer queries of variant paper_counting_rule_sp3_opacity for one boundary, reusing the
# scalar and slot-type query results of the run behind the paper's tables (those queries are not
# changed by the variant). Usage: sp3op-run.sh BENCHMARK DATABASE SOURCE_REPORTS_DIR
set -uo pipefail
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
REPO=/home/user/interspec-typed-allocator
b=$1; db=$2; src=$3
W=${SP3OP_WORK:-$S/c2-sp3-opacity-shipped}; root=$W/root; out=${SP3OP_OUT:-$S/sp3op-out-shipped-opacity}
mkdir -p $out
echo "$b start $(date -u +%FT%TZ) source=$src" >> $out/steps.txt
ln -sfn "$S/coverage-work/db/$db" "$root/db/$db"
rm -rf "$root/reports/$b"; mkdir -p "$root/reports/$b"
cp "$src/scalar_slots.bqrs" "$src/slot_type_breakdown.bqrs" "$root/reports/$b/"
cmd=(python3 scripts/run_slot_policy_analysis.py --database "db/$db" --benchmark "$b" --output-dir "reports/$b"
     --split-pointer-query --threads 4 --codeql $S/codeql-bundle/codeql/codeql --ram 10000 --max-disk-cache 4000
     --reuse-scalar-bqrs --reuse-types-bqrs)
if [[ -f "$REPO/evaluation/coverage/configs/$b.json" ]]; then
  mkdir -p "$root/coverage/configs"; cp "$REPO/evaluation/coverage/configs/$b.json" "$root/coverage/configs/"
  cmd+=(--manifest "coverage/configs/$b.json")
fi
(cd "$root" && echo "${cmd[*]}" > "$out/$b.command.txt" && timeout 21600 "${cmd[@]}" > "$out/$b.log" 2>&1)
code=$?
rm -rf "$out/$b"; mkdir -p "$out/$b"
cp "$root/reports/$b"/*.csv "$out/$b/" 2>/dev/null
echo "$b exit=$code $(date -u +%FT%TZ)" >> $out/steps.txt
# The query cache only speeds up repeated runs; it can fill the disk.
$S/codeql-bundle/codeql/codeql database cleanup --cache-cleanup=clear "$S/coverage-work/db/$db" >> "$out/$b.cleanup.log" 2>&1
exit $code
