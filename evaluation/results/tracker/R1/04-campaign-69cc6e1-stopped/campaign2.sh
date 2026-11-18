#!/usr/bin/env bash
# Second complete re-measurement, at the commit that changes how the registry
# records allocations (tracker items R1 to R4 and the P items they supersede).
# One driver for everything; restartable: a step recorded with exit=0 is skipped.
# Output in $S/camp2.
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
R=/home/user/interspec-typed-allocator
C=$S/camp2; mkdir -p $C
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
  mkdir -p "$C/$name"
  idle "$C/$name.loadavg-before.txt"
  echo "$name start $(date -u +%FT%TZ)" >> $C/steps.txt
  "$@" > "$C/$name.stdout.txt" 2> "$C/$name.stderr.txt"; local code=$?
  echo "$name exit=$code $(date -u +%FT%TZ)" >> $C/steps.txt
  return $code
}
# 0. the six port programs: build and checks at this commit
declare -A wvar=( [zip]=INTERSPEC_ZIP_WORK [png]=INTERSPEC_PNG_WORK [ucl]=INTERSPEC_UCL_WORK
  [vpx]=INTERSPEC_VPX_WORK [hash]=INTERSPEC_HASH_WORK [tls]=INTERSPEC_TLS_WORK )
build() { env "${wvar[$1]}=$S/c2-w-$1" bash scripts/run_${1}_port.sh $C/builds/$1/run; }
for p in zip png ucl vpx hash tls; do run builds/$p build $p || exit 1; done
for p in zip png ucl vpx hash tls; do (cd $S/c2-w-$p/bin && sha256sum *) > $C/builds/binaries-$p.sha256; done
declare -A bin=( [ffmpeg_libvpx]=vpx [magick_libpng]=png [memcached_hash]=hash [memcached_assoc]=hash
  [nginx_openssl]=tls [ucl_libucl]=ucl [zip_libzip]=zip [zip_libzip_listing]=zip )
declare -A corpus=( [ffmpeg_libvpx]=vpx [magick_libpng]=png [memcached_hash]=hash [memcached_assoc]=assoc
  [nginx_openssl]=tls [ucl_libucl]=ucl [zip_libzip]=zip [zip_libzip_listing]=zip_listing )
ports="zip_libzip zip_libzip_listing memcached_assoc magick_libpng memcached_hash ucl_libucl nginx_openssl ffmpeg_libvpx"
port() {  # port MODE BOUNDARY OUT
  python3 tools/benchmark_ports.py --boundary "$2" --mode "$1" --bin "$S/c2-w-${bin[$2]}/bin" \
    --corpus "evaluation/parity/${corpus[$2]}" --workloads evaluation/performance/port_workloads.json \
    --out "$3" --repetitions 15 --rounds 30 --cpu 0 --source-commit "$commit" --label "$label"
}
# 1. ports, four variants (P7 protocol)
for b in $ports; do run p7/$b port variants $b $C/p7/$b/run; done
# 2. ports, instruction counts
for b in $ports; do
  run instr/$b python3 tools/count_port_instructions.py --boundary $b --bin "$S/c2-w-${bin[$b]}/bin" \
    --corpus "evaluation/parity/${corpus[$b]}" --workloads evaluation/performance/port_workloads.json \
    --out $C/instr/$b/run --source-commit "$commit"; done
# 3. ports, per-policy cost (P6 protocol)
for b in $ports; do run p6-ports/$b port policies $b $C/p6-ports/$b/run; done
# 4. registry microbenchmarks: the P8 tool on the locked and the single-threaded build of this
#    commit and on the single-threaded build of the registry of 930cb20, and the token bench
mkdir -p $C/micro/bin $S/r1-930cb20
[ -d $S/r1-930cb20/include ] || git archive 930cb20 include | tar -x -C $S/r1-930cb20
run micro/p8-locked python3 tools/run_runtime_microbench.py --out $C/micro/p8-locked/run --repetitions 15 --cpus 0 --label "$label"
did micro/builds || { g++ -std=c++17 -O2 -pthread -DINTERSPEC_SINGLE_THREADED_REGISTRY -I include evaluation/runtime_bench.cpp -o $C/micro/bin/runtime_microbench_single > $C/micro/builds.log 2>&1 &&
  g++ -std=c++17 -O2 -pthread -DINTERSPEC_SINGLE_THREADED_REGISTRY -I $S/r1-930cb20/include evaluation/runtime_bench.cpp -o $C/micro/bin/runtime_microbench_single_930cb20 >> $C/micro/builds.log 2>&1 &&
  g++ -std=c++17 -O2 -pthread -I $S/r1-930cb20/include evaluation/runtime_bench.cpp -o $C/micro/bin/runtime_microbench_locked_930cb20 >> $C/micro/builds.log 2>&1
  echo "micro/builds exit=$?" >> $C/steps.txt; }
for v in single single_930cb20 locked_930cb20; do
  run micro/p8-$v python3 tools/run_runtime_microbench.py --out $C/micro/p8-$v/run --binary $C/micro/bin/runtime_microbench_$v --repetitions 15 --cpus 0 --label "$label"; done
ext() {  # 15 repetitions of the three builds, interleaved
  local o=$C/micro/ext/run; mkdir -p $o
  g++ -std=c++17 -O2 -pthread -I $S/r1-before/include evaluation/registry_external_bench.cpp -o $o/before || return 1
  g++ -std=c++17 -O2 -pthread -I include evaluation/registry_external_bench.cpp -o $o/after-locked || return 1
  g++ -std=c++17 -O2 -pthread -DINTERSPEC_SINGLE_THREADED_REGISTRY -I include evaluation/registry_external_bench.cpp -o $o/after-single || return 1
  git -C $S/r1-before rev-parse HEAD > $o/before-commit.txt
  for rep in $(seq 1 15); do for b in before after-locked after-single; do
    taskset -c 0 $o/$b > $o/$b.$rep.csv || return 1; done; done
}
run micro/ext ext
# 5. R2: magick/libpng binaries of three commits in one interleaved measurement
old=$S/r2-w-png-8fc7020/bin; mid=$S/r1d-w-png/bin; new=$S/c2-w-png/bin
png=evaluation/parity/png/basn4a16.png
variants() { echo "$1-rlbox-only=$2/png-rlbox-only@0,0,1 $1-tracked-no-check=$2/png-tracked-no-check@1,1,1 $1-interspec=$2/png-interspec@1,1,1 $1-interspec-all-off=$2/png-interspec@0,0,0"; }
run r2/time python3 tools/time_binaries.py $C/r2/time/run 15 30 new-rlbox-only native=$new/png-native \
  $(variants new $new) $(variants mid $mid) $(variants old $old) -- $png 700
(cd $old && sha256sum *) > $C/r2/binaries-old-8fc7020.sha256; (cd $mid && sha256sum *) > $C/r2/binaries-mid-930cb20.sha256
# 6. rsync/popt (P4) and yaml/libyaml (P5): each script builds, checks and times
export TMPDIR=$S/camp2-tmp; mkdir -p $TMPDIR
run p4 taskset -c 0 bash scripts/run_p11_wasm2c_performance.sh $C/p4/run
run p5 taskset -c 0 bash scripts/run_yaml_libyaml_evaluation.sh $C/p5/run
unset TMPDIR
rw=$S/camp2-tmp/interspec-p11-driver/interspec-rlbox-wasm2c; yw=$S/camp2-tmp/interspec-yaml-libyaml
# 7. R3: instruction counts of rsync/popt and yaml/libyaml, yaml in interleaved slices
did p4 && run r3/rsync python3 tools/count_application_instructions.py rsync --native $rw/rsync-p11-native --rlbox-only $rw/rsync-p11-rlbox-only \
  --interspec $rw/rsync-p11-extended-sp3 --scratch $S/camp2-r3-scratch-rsync --out $C/r3/rsync/run --source-commit "$commit"
did p5 && run r3/yaml python3 tools/count_application_instructions.py yaml --native $yw/yaml-native-bench --rlbox-only $yw/yaml-rlbox-bench \
  --interspec $yw/yaml-typed-bench --input $C/p5/run/document-1m.yaml --iterations 12 --out $C/r3/yaml/run --source-commit "$commit"
did p5 && run r3/yaml-sliced python3 tools/time_binaries.py $C/r3/yaml-sliced/run 15 30 rlbox-only \
  native=$yw/yaml-native-bench rlbox-only=$yw/yaml-rlbox-bench@0,0,1@rlbox_only \
  tracked-no-check=$yw/yaml-typed-bench@1,1,1@tracked_no_check interspec=$yw/yaml-typed-bench@1,1,1@extended_sp3 -- $C/p5/run/document-1m.yaml 12
# 8. nginx/libpcre: build, gate, timing (P3)
nginxbuild() { INTERSPEC_NGINX_WORK=$S/camp2-nginx-work bash scripts/build_nginx_deployment.sh $S/camp2-nginx-work; }
run nginx-build nginxbuild
p3() { local o=$C/p3/run; mkdir -p $o
  python3 tools/test_nginx_deployment.py --work $S/camp2-nginx-work --out $o/gate > $o/gate.stdout.txt 2> $o/gate.stderr.txt || return 1
  python3 tools/benchmark_nginx.py --work $S/camp2-nginx-work --out $o/timing --correctness $o/gate/summary.json \
    --threads 4 8 --repetitions 15 --server-cpus 0-1 --client-cpus 2-3; }
did nginx-build && run p3 p3
# 9. memcached/bipbuffer (P2): its own restartable driver
did p2 || { idle $C/p2.loadavg-before.txt; echo "p2 start $(date -u +%FT%TZ)" >> $C/steps.txt
  bash $S/camp2-p2.sh > $C/p2.stdout.txt 2> $C/p2.stderr.txt; code=$?
  [ -f $S/camp2-p2-out/DONE ] && grep -q '^verify exit=0' $S/camp2-p2-out/steps.txt || code=1
  echo "p2 exit=$code $(date -u +%FT%TZ)" >> $C/steps.txt; }
mw=$S/camp2-p2-tmp/interspec-memcached-deployment
# 10. per-policy cost on the four applications (P6 protocol)
p6app() { local b=$1; shift
  python3 tools/benchmark_policy_cost.py $b --out $C/p6-apps/$b/run --scratch $S/camp2-p6-scratch-$b --repetitions 15 \
    --label "$label" --source-commit "$commit" "$@"; }
did p4 && run p6-apps/rsync p6app rsync --rlbox-only $rw/rsync-p11-rlbox-only --interspec $rw/rsync-p11-extended-sp3 --cpu 0 --rounds option_parse=100 file_sync_194mb=8
did p5 && run p6-apps/yaml p6app yaml --rlbox-only $yw/yaml-rlbox-bench --interspec $yw/yaml-typed-bench --cpu 0 --input $C/p5/run/document-1m.yaml --iterations 12 --rounds yaml_parse_1mb=30
did p3 && run p6-apps/nginx p6app nginx --work $S/camp2-nginx-work --seconds 2 --warmup 1 --rounds regex_location_4_threads=6
did p2 && run p6-apps/memcached p6app memcached --work $mw --client $S/camp2-p2-client --seconds 2 --warmup 1 --rounds watch_moderate=6
# 11. memory (P9)
mem() { python3 tools/measure_memory_cost.py run --application $1 --variant $2 --work "$3" --client $S/camp2-p2-client \
    --out $C/p9/$1-$2/run --seconds 600 --interval 5 --label "$label" --source-commit "$commit"; }
for v in native rlbox-only interspec; do did p2 && run p9/memcached-$v mem memcached $v $mw; did p3 && run p9/nginx-$v mem nginx $v $S/camp2-nginx-work; done
echo "campaign end $(date -u +%FT%TZ)" >> $C/steps.txt; touch $C/DONE
