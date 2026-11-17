#!/usr/bin/env bash
# Re-measurement of every timing item at one commit (tracker items R1, R3 and the
# P items they supersede). Restartable: a step recorded with exit=0 is skipped.
# Usage: campaign.sh   (output in $S/camp)
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
R=/home/user/interspec-typed-allocator
C=$S/camp; mkdir -p $C
cd "$R" || exit 1
label="Claude Code cloud VM (KVM guest, 4 vCPUs, not a dedicated host)"
[ -f $C/steps.txt ] || { echo "commit $(git rev-parse HEAD)" > $C/steps.txt; git status --porcelain > $C/git-status-at-start.txt; }
commit=$(sed -n 's/^commit //p' $C/steps.txt | cut -c1-7)
[ "$(git rev-parse --short=7 HEAD)" = "$commit" ] || { echo "HEAD moved from $commit" >> $C/steps.txt; exit 1; }
export INTERSPEC_BUILD_JOBS=4 INTERSPEC_WASM_DEPS=$S/nginx-work/wasm-deps
nap() { python3 -c "import time; time.sleep($1)"; }
idle() { for i in $(seq 1 80); do python3 -c "import sys; sys.exit(0 if float(open('/proc/loadavg').read().split()[0]) < 0.30 else 1)" && break; nap 15; done; cat /proc/loadavg > "$1"; }
did() { grep -q "^$1 exit=0" $C/steps.txt; }
run() {  # run NAME COMMAND...: once, on an idle machine, with stdout/stderr and status kept
  local name=$1; shift
  did "$name" && return 0
  [ -e "$C/$name" ] && mv "$C/$name" "$C/$name.failed-$(date -u +%H%M%S)"
  idle "$C/$name.loadavg-before.txt"
  echo "$name start $(date -u +%FT%TZ)" >> $C/steps.txt
  "$@" > "$C/$name.stdout.txt" 2> "$C/$name.stderr.txt"; local code=$?
  echo "$name exit=$code $(date -u +%FT%TZ)" >> $C/steps.txt
  return $code
}
declare -A bin=( [ffmpeg_libvpx]=r1d-w-vpx [magick_libpng]=r1d-w-png [memcached_hash]=r1d-w-hash
  [memcached_assoc]=r1d-w-hash [nginx_openssl]=r1d-w-tls [ucl_libucl]=r1d-w-ucl [zip_libzip]=r1d-w-zip )
declare -A corpus=( [ffmpeg_libvpx]=vpx [magick_libpng]=png [memcached_hash]=hash
  [memcached_assoc]=assoc [nginx_openssl]=tls [ucl_libucl]=ucl [zip_libzip]=zip )
ports="zip_libzip memcached_assoc magick_libpng memcached_hash ucl_libucl nginx_openssl ffmpeg_libvpx"
port() {  # port MODE BOUNDARY OUT
  python3 tools/benchmark_ports.py --boundary "$2" --mode "$1" --bin "$S/${bin[$2]}/bin" \
    --corpus "evaluation/parity/${corpus[$2]}" --workloads evaluation/performance/port_workloads.json \
    --out "$3" --repetitions 15 --rounds 30 --cpu 0 --source-commit "$commit" --label "$label"
}
# 1. ports, four variants (P7 protocol)
mkdir -p $C/p7; for b in $ports; do run p7/$b port variants $b $C/p7/$b/run; done
for p in zip png ucl vpx hash tls; do (cd $S/r1d-w-$p/bin && sha256sum *) > $C/p7/binaries-$p.sha256; done
# 2. ports, instruction counts
mkdir -p $C/instr; for b in $ports; do
  run instr/$b python3 tools/count_port_instructions.py --boundary $b --bin "$S/${bin[$b]}/bin" \
    --corpus "evaluation/parity/${corpus[$b]}" --workloads evaluation/performance/port_workloads.json \
    --out $C/instr/$b/run --source-commit "$commit"; done
# 3. registry microbenchmarks: the P8 tool (locked and single-threaded build) and the token bench
mkdir -p $C/micro
run micro/p8-locked python3 tools/run_runtime_microbench.py --out $C/micro/p8-locked/run --repetitions 15 --cpus 0 --label "$label"
did micro/p8-single-build || { mkdir -p $C/micro/bin; g++ -std=c++17 -O2 -pthread -DINTERSPEC_SINGLE_THREADED_REGISTRY -I include evaluation/runtime_bench.cpp -o $C/micro/bin/runtime_microbench_single > $C/micro/p8-single-build.log 2>&1; echo "micro/p8-single-build exit=$?" >> $C/steps.txt; }
run micro/p8-single python3 tools/run_runtime_microbench.py --out $C/micro/p8-single/run --binary $C/micro/bin/runtime_microbench_single --repetitions 15 --cpus 0 --label "$label"
ext() {  # 15 repetitions of the three builds, interleaved
  mkdir -p $C/micro/ext/run; local o=$C/micro/ext/run
  g++ -std=c++17 -O2 -pthread -I $S/r1-before/include evaluation/registry_external_bench.cpp -o $o/before || return 1
  g++ -std=c++17 -O2 -pthread -I include evaluation/registry_external_bench.cpp -o $o/after-locked || return 1
  g++ -std=c++17 -O2 -pthread -DINTERSPEC_SINGLE_THREADED_REGISTRY -I include evaluation/registry_external_bench.cpp -o $o/after-single || return 1
  git -C $S/r1-before rev-parse HEAD > $o/before-commit.txt
  for rep in $(seq 1 15); do for b in before after-locked after-single; do
    taskset -c 0 $o/$b > $o/$b.$rep.csv || return 1; done; done
}
run micro/ext ext
# 4. ports, per-policy cost (P6 protocol)
mkdir -p $C/p6-ports; for b in $ports; do run p6-ports/$b port policies $b $C/p6-ports/$b/run; done
# 5. nginx/libpcre: build, gate, timing (P3)
run nginx-build bash scripts/build_nginx_deployment.sh $S/camp-nginx-work
p3() { local o=$C/p3/run; mkdir -p $o
  python3 tools/test_nginx_deployment.py --work $S/camp-nginx-work --out $o/gate > $o/gate.stdout.txt 2> $o/gate.stderr.txt || return 1
  python3 tools/benchmark_nginx.py --work $S/camp-nginx-work --out $o/timing --correctness $o/gate/summary.json \
    --threads 4 8 --repetitions 15 --server-cpus 0-1 --client-cpus 2-3; }
mkdir -p $C/p3; did nginx-build && run p3 p3
# 6. rsync/popt (P4) and yaml/libyaml (P5): each script builds, checks and times
export TMPDIR=$S/camp-tmp; mkdir -p $TMPDIR
mkdir -p $C/p4 $C/p5
run p4 taskset -c 0 bash scripts/run_p11_wasm2c_performance.sh $C/p4/run
run p5 taskset -c 0 bash scripts/run_yaml_libyaml_evaluation.sh $C/p5/run
unset TMPDIR
# 7. memcached/bipbuffer (P2): its own restartable driver
did p2 || { idle $C/p2.loadavg-before.txt; echo "p2 start $(date -u +%FT%TZ)" >> $C/steps.txt
  bash $S/camp-p2.sh > $C/p2.stdout.txt 2> $C/p2.stderr.txt; code=$?
  [ -f $S/camp-p2-out/DONE ] && grep -q '^verify exit=0' $S/camp-p2-out/steps.txt || code=1
  echo "p2 exit=$code $(date -u +%FT%TZ)" >> $C/steps.txt; }
# 8. per-policy cost on the four applications (P6 protocol)
rw=$S/camp-tmp/interspec-p11-driver/interspec-rlbox-wasm2c; yw=$S/camp-tmp/interspec-yaml-libyaml
mw=$S/camp-p2-tmp/interspec-memcached-deployment
p6app() { local b=$1; shift
  python3 tools/benchmark_policy_cost.py $b --out $C/p6-apps/$b/run --scratch $S/camp-p6-scratch-$b --repetitions 15 \
    --label "$label" --source-commit "$commit" "$@"; }
mkdir -p $C/p6-apps
did p4 && run p6-apps/rsync p6app rsync --rlbox-only $rw/rsync-p11-rlbox-only --interspec $rw/rsync-p11-extended-sp3 --cpu 0 --rounds option_parse=100 file_sync_194mb=8
did p5 && run p6-apps/yaml p6app yaml --rlbox-only $yw/yaml-rlbox-bench --interspec $yw/yaml-typed-bench --cpu 0 --input $C/p5/run/document-1m.yaml --iterations 12 --rounds yaml_parse_1mb=30
did p3 && run p6-apps/nginx p6app nginx --work $S/camp-nginx-work --seconds 2 --warmup 1 --rounds regex_location_4_threads=6
did p2 && run p6-apps/memcached p6app memcached --work $mw --client $S/camp-p2-client --seconds 2 --warmup 1 --rounds watch_moderate=6
# 9. memory (P9)
mem() { python3 tools/measure_memory_cost.py run --application $1 --variant $2 --work "$3" --client $S/camp-p2-client \
    --out $C/p9/$1-$2/run --seconds 600 --interval 5 --label "$label" --source-commit "$commit"; }
mkdir -p $C/p9
for v in native rlbox-only interspec; do did p2 && run p9/memcached-$v mem memcached $v $mw; did p3 && run p9/nginx-$v mem nginx $v $S/camp-nginx-work; done
echo "campaign end $(date -u +%FT%TZ)" >> $C/steps.txt; touch $C/DONE
