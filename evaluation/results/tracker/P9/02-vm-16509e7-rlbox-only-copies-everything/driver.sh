#!/usr/bin/env bash
# Runs after the memcached rerun: yaml/libyaml (P5) once on an idle machine, then the memory runs (P9).
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
R=/home/user/interspec-typed-allocator
O=$S/after-p2-out; mkdir -p $O
step() { echo "$1 $(date -u +%FT%TZ)" >> $O/steps.txt; }
nap() { python3 -c "import time; time.sleep($1)"; }
idle() {  # wait until the 1-minute load average is below 0.30, at most 40 minutes; record what was seen
  for i in $(seq 1 160); do
    l=$(cut -d' ' -f1 /proc/loadavg)
    if python3 -c "import sys; sys.exit(0 if float('$l') < 0.30 else 1)"; then break; fi
    nap 15
  done
  cat /proc/loadavg > "$1"
}
# 1. wait for the memcached driver
while [ ! -f $S/p2-rerun2-out/DONE ] && kill -0 4325 2>/dev/null; do nap 10; done
[ -f $S/p2-rerun2-out/DONE ] || { step "memcached driver ended without DONE; nothing started"; exit 1; }
step "memcached done"
cd $R || exit 1
git status --porcelain > $O/git-status.txt
commit=$(git rev-parse --short HEAD); echo "commit $commit" >> $O/steps.txt
# 2. yaml/libyaml
Y=$O/yaml; mkdir -p $Y
idle $Y/loadavg-before.txt
step "yaml start"
TMPDIR=$S/rerun-tmp taskset -c 0 bash scripts/run_yaml_libyaml_evaluation.sh $Y/run > $Y/runner.stdout.txt 2> $Y/runner.stderr.txt
echo "run exit=$?" >> $Y/steps.txt; echo "commit $commit" >> $Y/steps.txt
cat /proc/loadavg > $Y/loadavg-after.txt
step "yaml end ($(cat $Y/steps.txt | head -1))"
# 3. memory: all three memcached variants (new build), nginx RLBox-only (same binary as P9 run 01)
M=$O/memory; mkdir -p $M
label="Claude Code cloud VM (KVM guest, 4 vCPUs, not a dedicated host)"
for pair in memcached:native memcached:rlbox-only memcached:interspec nginx:rlbox-only; do
  app=${pair%%:*}; variant=${pair##*:}
  if [ $app = memcached ]; then work=$S/p2-rerun2-tmp/interspec-memcached-deployment; else work=$S/nginx-work; fi
  idle $M/loadavg-before-$app-$variant.txt
  python3 tools/measure_memory_cost.py run --application $app --variant $variant --work "$work" \
    --client "$S/p2-rerun2-client" --out "$M/$app-$variant" --seconds 600 --interval 5 \
    --label "$label" --source-commit "$commit" > "$M/$app-$variant.stdout.txt" 2> "$M/$app-$variant.stderr.txt"
  echo "$app $variant exit=$? $(date -u +%T)" >> $M/steps.txt
done
step "memory end"
touch $O/DONE
