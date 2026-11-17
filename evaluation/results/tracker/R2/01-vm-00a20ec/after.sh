#!/usr/bin/env bash
# Measurements after the campaign (tracker items R2, R3, R4 and the three
# per-policy application steps whose gate had a stale comparison).
# Restartable like campaign.sh; output in $S/after.
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
R=/home/user/interspec-typed-allocator
C=$S/after; mkdir -p $C
cd "$R" || exit 1
label="Claude Code cloud VM (KVM guest, 4 vCPUs, not a dedicated host)"
[ -f $C/steps.txt ] || { echo "commit $(git rev-parse HEAD)" > $C/steps.txt; git status --porcelain > $C/git-status-at-start.txt; }
commit=$(sed -n 's/^commit //p' $C/steps.txt | cut -c1-7)
[ "$(git rev-parse --short=7 HEAD)" = "$commit" ] || { echo "HEAD moved from $commit" >> $C/steps.txt; exit 1; }
export INTERSPEC_BUILD_JOBS=4 INTERSPEC_WASM_DEPS=$S/nginx-work/wasm-deps
nap() { python3 -c "import time; time.sleep($1)"; }
idle() { for i in $(seq 1 80); do python3 -c "import sys; sys.exit(0 if float(open('/proc/loadavg').read().split()[0]) < 0.30 else 1)" && break; nap 15; done; cat /proc/loadavg > "$1"; }
did() { grep -q "^$1 exit=0" $C/steps.txt; }
run() {
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
# 1. per-policy cost on rsync, nginx, memcached: binaries of the campaign (930cb20), gate of this commit
rw=$S/camp-tmp/interspec-p11-driver/interspec-rlbox-wasm2c; yw=$S/camp-tmp/interspec-yaml-libyaml
mw=$S/camp-p2-tmp/interspec-memcached-deployment
p6app() { local b=$1; shift
  python3 tools/benchmark_policy_cost.py $b --out $C/p6-apps/$b/run --scratch $S/after-p6-scratch-$b --repetitions 15 \
    --label "$label" --source-commit "930cb20 (binaries), $commit (tool)" "$@"; }
run p6-apps/rsync p6app rsync --rlbox-only $rw/rsync-p11-rlbox-only --interspec $rw/rsync-p11-extended-sp3 --cpu 0 --rounds option_parse=100 file_sync_194mb=8
run p6-apps/nginx p6app nginx --work $S/camp-nginx-work --seconds 2 --warmup 1 --rounds regex_location_4_threads=6
run p6-apps/memcached p6app memcached --work $mw --client $S/camp-p2-client --seconds 2 --warmup 1 --rounds watch_moderate=6
# 2. R2: magick/libpng binaries of the earlier measurement (8fc7020) against those of the campaign
old=$S/r2-w-png-8fc7020; new=$S/r1d-w-png
r2build() { (cd $S/r2-src-8fc7020 && INTERSPEC_PNG_WORK=$old bash scripts/run_png_port.sh $C/r2/build-8fc7020/run); }
run r2/build-8fc7020 r2build
png=evaluation/parity/png/basn4a16.png
did r2/build-8fc7020 && run r2/time python3 tools/time_binaries.py $C/r2/time/run 15 30 new-rlbox-only \
  native=$new/bin/png-native new-rlbox-only=$new/bin/png-rlbox-only@0,0,1 new-tracked-no-check=$new/bin/png-tracked-no-check@1,1,1 \
  new-interspec=$new/bin/png-interspec@1,1,1 old-rlbox-only=$old/bin/png-rlbox-only@0,0,1 \
  old-tracked-no-check=$old/bin/png-tracked-no-check@1,1,1 old-interspec=$old/bin/png-interspec@1,1,1 -- $png 700
did r2/build-8fc7020 && run r2/instr-8fc7020 python3 tools/count_port_instructions.py --boundary magick_libpng --bin $old/bin \
  --corpus evaluation/parity/png --workloads evaluation/performance/port_workloads.json --out $C/r2/instr-8fc7020/run --source-commit 8fc7020
# 3. R4: zip/libzip listing workload (new build of the zip port at this commit)
zw=$S/r4-w-zip
r4build() { INTERSPEC_ZIP_WORK=$zw bash scripts/run_zip_port.sh $C/r4/build/run; }
run r4/build r4build
port() { python3 tools/benchmark_ports.py --boundary "$2" --mode "$1" --bin $zw/bin \
    --corpus "evaluation/parity/$3" --workloads evaluation/performance/port_workloads.json \
    --out "$4" --repetitions 15 --rounds 30 --cpu 0 --source-commit "$commit" --label "$label"; }
instr() { python3 tools/count_port_instructions.py --boundary $1 --bin $zw/bin --corpus evaluation/parity/$2 \
    --workloads evaluation/performance/port_workloads.json --out $3 --source-commit "$commit"; }
if did r4/build; then
  run r4/p7-listing port variants zip_libzip_listing zip_listing $C/r4/p7-listing/run
  run r4/p6-listing port policies zip_libzip_listing zip_listing $C/r4/p6-listing/run
  run r4/instr-listing instr zip_libzip_listing zip_listing $C/r4/instr-listing/run
  run r4/instr-query instr zip_libzip zip $C/r4/instr-query/run
fi
# 4. R3: instruction counts of rsync/popt and yaml/libyaml (binaries of the campaign)
run r3/rsync python3 tools/count_application_instructions.py rsync --native $rw/rsync-p11-native --rlbox-only $rw/rsync-p11-rlbox-only \
  --interspec $rw/rsync-p11-extended-sp3 --scratch $S/after-r3-scratch-rsync --out $C/r3/rsync/run --source-commit 930cb20
run r3/yaml python3 tools/count_application_instructions.py yaml --native $yw/yaml-native-bench --rlbox-only $yw/yaml-rlbox-bench \
  --interspec $yw/yaml-typed-bench --input $S/camp/p5/run/document-1m.yaml --iterations 12 --out $C/r3/yaml/run --source-commit 930cb20
run r3/yaml-sliced python3 tools/time_binaries.py $C/r3/yaml-sliced/run 15 30 rlbox-only \
  native=$yw/yaml-native-bench rlbox-only=$yw/yaml-rlbox-bench@0,0,1@rlbox_only \
  tracked-no-check=$yw/yaml-typed-bench@1,1,1@tracked_no_check interspec=$yw/yaml-typed-bench@1,1,1@extended_sp3 -- $S/camp/p5/run/document-1m.yaml 12
echo "after end $(date -u +%FT%TZ)" >> $C/steps.txt; touch $C/DONE
