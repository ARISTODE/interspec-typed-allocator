#!/usr/bin/env bash
# P2 driver: build, correctness gate, timed matrix, verifier. One run; every
# step's output and exit status is kept.
set -uo pipefail
cd /home/user/interspec-typed-allocator
E=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad/p2-out-5037e6d
export TMPDIR=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad/p2-tmp-5037e6d
mkdir -p "$TMPDIR"
echo "commit 5037e6d" > $E/steps.txt
cat /proc/loadavg > $E/loadavg-before.txt
bash scripts/build_memcached_deployment.sh > $E/build.log 2>&1; code=$?; echo "build exit=$code" >> $E/steps.txt
if [[ $code == 0 ]]; then
  python3 tools/test_memcached_deployment.py --out $E/correctness > $E/correctness.stdout.txt 2> $E/correctness.stderr.txt; code=$?; echo "correctness exit=$code" >> $E/steps.txt
fi
if [[ $code == 0 ]]; then
  cat /proc/loadavg > $E/loadavg-before-matrix.txt
  python3 tools/benchmark_memcached_matrix.py --out $E/matrix --preset paper --include-tracking \
    --server-cpus 0-1 --client-cpus 2-3 --correctness-summary $E/correctness/summary.json \
    --label "Claude Code cloud VM (KVM guest, 4 vCPUs, not a dedicated host)" \
    > $E/matrix.stdout.txt 2> $E/matrix.stderr.txt; code=$?; echo "matrix exit=$code" >> $E/steps.txt
  cat /proc/loadavg > $E/loadavg-after-matrix.txt
fi
if [[ $code == 0 ]]; then
  python3 tools/verify_memcached_matrix.py --matrix $E/matrix --correctness-summary $E/correctness/summary.json \
    > $E/verify.stdout.txt 2> $E/verify.stderr.txt; code=$?; echo "verify exit=$code" >> $E/steps.txt
fi
echo "overall exit=$code" >> $E/steps.txt
touch $E/DONE
