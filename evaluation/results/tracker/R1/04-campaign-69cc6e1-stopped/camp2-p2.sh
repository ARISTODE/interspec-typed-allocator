#!/usr/bin/env bash
# P2 rerun (RLBox-only copies everything): build, gate, checkpointed matrix one
# scenario per block, verifier. Every step's output and exit status is kept.
# Restartable: steps already recorded as exit=0 are skipped.
set -uo pipefail
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
cd /home/user/interspec-typed-allocator
E=$S/camp2-p2-out; ST=$S/camp2-p2-state
export TMPDIR=$S/camp2-p2-tmp
W=$TMPDIR/interspec-memcached-deployment
mkdir -p "$E" "$TMPDIR"
step() { echo "$1 $(date -u +%FT%T)" >> $E/steps.txt; }
done_ok() { grep -q "^$1 exit=0 " $E/steps.txt 2>/dev/null; }
[ -f $E/steps.txt ] || echo "commit $(git rev-parse HEAD)" > $E/steps.txt
if ! done_ok build; then
  cat /proc/loadavg > $E/loadavg-before-build.txt
  git status --porcelain > $E/git-status-before-build.txt; [ -s $E/git-status-before-build.txt ] && { step "tree not clean before build"; exit 1; }
  bash scripts/build_memcached_deployment.sh > $E/build.log 2>&1; code=$?; step "build exit=$code"; [ $code -eq 0 ] || exit 1
  git status --porcelain > $E/git-status-after-build.txt
  grep -q '"project_dirty": false' $W/build-manifest.json || { step "build record says dirty"; exit 1; }
fi
if ! done_ok correctness; then
  python3 tools/test_memcached_deployment.py --work $W --out $E/correctness > $E/correctness.stdout.txt 2> $E/correctness.stderr.txt; code=$?; step "correctness exit=$code"; [ $code -eq 0 ] || exit 1
fi
if ! done_ok init; then
  g++ -std=c++17 -O2 -pthread evaluation/memcached_client.cpp -o $S/camp2-p2-client > $E/client-build.log 2>&1 || { step "client-build exit=1"; exit 1; }
  rm -rf $ST
  python3 tools/benchmark_memcached_matrix.py checkpoint init $ST --work $W --correctness-summary $E/correctness/summary.json \
    --client-binary $S/camp2-p2-client --allow-one-interruption-replacement -- --preset paper --server-cpus 0-1 --client-cpus 2-3 \
    --label "Claude Code cloud VM (KVM guest, 4 vCPUs, not a dedicated host)" > $E/init.stdout.txt 2> $E/init.stderr.txt; code=$?; step "init exit=$code"; [ $code -eq 0 ] || exit 1
fi
for block in 1 2 3 4 5 6; do
  done_ok "block-$block" && continue
  cat /proc/loadavg > $E/loadavg-before-block-$block.txt
  step "block-$block start"
  python3 $ST/tools/benchmark_memcached_matrix.py checkpoint run $ST --max-scenarios 1 > $E/block-$block.stdout.txt 2> $E/block-$block.stderr.txt; code=$?
  step "block-$block exit=$code"; [ $code -eq 0 ] || exit 1
  grep -q '"grid_complete": true' $E/block-$block.stdout.txt && break
done
# A run whose last scenario was just measured returns "pending"; one more call writes the report.
if ! grep -qs '"grid_complete": true' $E/block-*.stdout.txt; then
  python3 $ST/tools/benchmark_memcached_matrix.py checkpoint run $ST --max-scenarios 1 > $E/block-final.stdout.txt 2> $E/block-final.stderr.txt; code=$?
  step "block-final exit=$code"; [ $code -eq 0 ] || exit 1
fi
REP=$(grep -hs '"report"' $E/block-*.stdout.txt | tail -1 | sed 's/.*: "\(.*\)",/\1/')
echo "$REP" > $E/report-path.txt
python3 tools/verify_memcached_matrix.py --matrix "$REP" --correctness-summary $ST/correctness.json > $E/verifier.stdout.txt 2>&1; code=$?; step "verify exit=$code"
touch $E/DONE
