#!/usr/bin/env bash
# Re-measurement of the eight library workloads after the switch-accessor fix (tracker Log, 2026-11-19):
# port builds and checks, alignment gate, p7, instruction counts, per-policy runs. Same commands as
# campaign3.sh, with the speed check of campaign3b.sh before every step. Output in $S/camp3c.
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
R=/home/user/interspec-typed-allocator
C=$S/camp3c; mkdir -p $C
cd "$R" || exit 1
label="Claude Code cloud VM (KVM guest, 4 vCPUs, not a dedicated host)"
[ -f $C/steps.txt ] || { echo "commit $(git rev-parse HEAD)" > $C/steps.txt; git status --porcelain > $C/git-status-at-start.txt; }
commit=$(sed -n 's/^commit //p' $C/steps.txt | cut -c1-7)
[ "$(git rev-parse --short=7 HEAD)" = "$commit" ] || { echo "HEAD moved from $commit" >> $C/steps.txt; exit 1; }
mkdir -p $C/builds
export INTERSPEC_BUILD_JOBS=4 INTERSPEC_WASM_DEPS=$S/nginx-work/wasm-deps
export PATH="$(bash scripts/aligned_compilers.sh $S/camp3-cc):$PATH"
echo "compilers: $(command -v cc) $(command -v g++)" > $C/compilers.txt; cat $S/camp3-cc/cc >> $C/compilers.txt
# aligned DIR NAME: check every executable under DIR that holds wasm2c code
aligned() { local list; list=$(find "$1" -maxdepth 4 -type f -perm -u+x -size +20k 2>/dev/null | while read -r f; do nm --defined-only "$f" 2>/dev/null | grep -q ' [tT] w2c_' && echo "$f"; done)
  [ -n "$list" ] || { echo "no executable with wasm2c code under $1" > $C/align-$2.txt; return 1; }
  python3 tools/check_function_alignment.py $list > $C/align-$2.txt 2>&1; }
nap() { python3 -c "import time; time.sleep($1)"; }
idle() { bash $S/quiet_gate.sh "$1" || { echo "not quiet after 8 hours: $1" >> $C/steps.txt; exit 1; }; }
after() { bash $S/quiet_gate.sh "$1" report; }
did() { grep -q "^$1 exit=0" $C/steps.txt; }
run() {  # run NAME COMMAND...: once, on an idle machine, with stdout/stderr and status kept
  local name=$1; shift
  did "$name" && return 0
  [ -e "$C/$name" ] && mv "$C/$name" "$C/$name.failed-$(date -u +%H%M%S)"
  mkdir -p "$C/$name"
  [ "${GATE:-1}" = 1 ] && idle "$C/$name.quiet-before.txt"
  echo "$name start $(date -u +%FT%TZ)" >> $C/steps.txt
  "$@" > "$C/$name.stdout.txt" 2> "$C/$name.stderr.txt"; local code=$?
  echo "$name exit=$code $(date -u +%FT%TZ)" >> $C/steps.txt
  [ "${GATE:-1}" = 1 ] && after "$C/$name.quiet-after.txt"
  return $code
}
# 0. the six port programs: build and checks at this commit
declare -A wvar=( [zip]=INTERSPEC_ZIP_WORK [png]=INTERSPEC_PNG_WORK [ucl]=INTERSPEC_UCL_WORK
  [vpx]=INTERSPEC_VPX_WORK [hash]=INTERSPEC_HASH_WORK [tls]=INTERSPEC_TLS_WORK )
build() { env "${wvar[$1]}=$S/c4-w-$1" bash scripts/run_${1}_port.sh $C/builds/$1/run; }
for p in zip png ucl vpx hash tls; do run builds/$p build $p || exit 1; done
for p in zip png ucl vpx hash tls; do (cd $S/c4-w-$p/bin && sha256sum *) > $C/builds/binaries-$p.sha256; done
for p in zip png ucl vpx hash tls; do aligned $S/c4-w-$p/bin port-$p || { echo "align port-$p failed" >> $C/steps.txt; exit 1; }; done
echo "align ports ok" >> $C/steps.txt
declare -A bin=( [ffmpeg_libvpx]=vpx [magick_libpng]=png [memcached_hash]=hash [memcached_assoc]=hash
  [nginx_openssl]=tls [ucl_libucl]=ucl [zip_libzip]=zip [zip_libzip_listing]=zip )
declare -A corpus=( [ffmpeg_libvpx]=vpx [magick_libpng]=png [memcached_hash]=hash [memcached_assoc]=assoc
  [nginx_openssl]=tls [ucl_libucl]=ucl [zip_libzip]=zip [zip_libzip_listing]=zip_listing )
ports="zip_libzip zip_libzip_listing memcached_assoc magick_libpng memcached_hash ucl_libucl nginx_openssl ffmpeg_libvpx"
port() {  # port MODE BOUNDARY OUT
  python3 tools/benchmark_ports.py --boundary "$2" --mode "$1" --bin "$S/c4-w-${bin[$2]}/bin" \
    --corpus "evaluation/parity/${corpus[$2]}" --workloads evaluation/performance/port_workloads.json \
    --out "$3" --repetitions 15 --rounds 30 --cpu 0 --source-commit "$commit" --label "$label"
}
# 1. ports, four variants (P7 protocol)
for b in $ports; do run p7/$b port variants $b $C/p7/$b/run; done
# 2. ports, instruction counts
for b in $ports; do
  GATE=0 run instr/$b python3 tools/count_port_instructions.py --boundary $b --bin "$S/c4-w-${bin[$b]}/bin" \
    --corpus "evaluation/parity/${corpus[$b]}" --workloads evaluation/performance/port_workloads.json \
    --out $C/instr/$b/run --source-commit "$commit"; done
# 3. ports, per-policy cost (P6 protocol)
for b in $ports; do run p6-ports/$b port policies $b $C/p6-ports/$b/run; done
echo "campaign end $(date -u +%FT%TZ)" >> $C/steps.txt; touch $C/DONE
