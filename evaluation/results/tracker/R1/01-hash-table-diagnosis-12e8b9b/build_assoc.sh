#!/usr/bin/env bash
# build_assoc.sh OUTDIR INCLUDE_ROOT [extra g++ flags]: the three host variants of the hash table
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
out=$1; inc=$2; shift 2
deps=$S/nginx-work/wasm-deps; wabt=$deps/build/_deps/wasm2c_compiler-src; w=$S/r1c-w-hash
dir=${ASSOC_DIR:-/home/user/interspec-typed-allocator/integration/memcached_hash}
mkdir -p $out
b() { g++ -std=c++17 -O2 -DWASM_RT_USE_MMAP=1 -DWASM_RT_SKIP_SIGNAL_RECOVERY=1 -DWASM_RT_NONCONFORMING_UNCHECKED_STACK_EXHAUSTION=1 \
  -I$deps/include -I$deps/build/_deps/rlbox-src/code/include -I$wabt/wasm2c -I$wabt/third_party/simde -I$inc -I$w/assoc \
  -DINTERSPEC_TRACKING=0 -DINTERSPEC_CHECKS=$2 -I/home/user/interspec-typed-allocator/integration/memcached_hash "${@:3}" $dir/assoc_app_bench.cpp $w/assoc/module.a -pthread -ldl -lrt -lm -o $out/assoc-$1; }
b rlbox-only 0 "$@" & b interspec 1 "$@" & b tracked-no-check 0 -DINTERSPEC_T_TRACKING=1 "$@" & wait
