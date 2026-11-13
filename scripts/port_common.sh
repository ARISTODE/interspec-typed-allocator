# Shared build steps for the registry ports (EVAL_TRACKER.md items I7 to I12).
# Sourced by scripts/run_<boundary>_port.sh. Expects $root (repository) and
# $work (build directory) to be set.

port_deps() {  # the pinned RLBox wasm2c backend, wasi clang and wasm2c
  deps=${INTERSPEC_WASM_DEPS:-$work/wasm-deps}
  if [[ ! -d "$deps/.git" ]]; then
    git clone -q https://github.com/PLSysSec/rlbox_wasm2c_sandbox.git "$deps" || return 1
    git -C "$deps" checkout -q c4f18c48cea47421617f72ba5edc95c68aa85671 || return 1
    python3 "$root/backends/rlbox_wasm2c/apply_backend.py" --root "$deps" || return 1
  fi
  [[ $(git -C "$deps" rev-parse HEAD) == c4f18c48cea47421617f72ba5edc95c68aa85671 ]] || return 1
  if [[ ! -f "$deps/build/libglue_lib_imported.a" ]]; then
    cmake -S "$deps" -B "$deps/build" -DCMAKE_BUILD_TYPE=Release || return 1
    cmake --build "$deps/build" --target glue_lib_imported -j"${INTERSPEC_BUILD_JOBS:-2}" || return 1
  fi
  wabt="$deps/build/_deps/wasm2c_compiler-src"
  wasi="$deps/build/_deps/wasiclang-src"
  [[ $(git -C "$deps/build/_deps/rlbox-src" rev-parse HEAD) == b0157dc84f86ffbe4549e32ed5cbdfad79c17f43 ]] || return 1
  [[ $(git -C "$wabt" rev-parse HEAD) == 974221b1ef82f6393d004e5da6116f2ad3e44005 ]] || return 1
  host_defines=(-DWASM_RT_USE_MMAP=1 -DWASM_RT_SKIP_SIGNAL_RECOVERY=1
                -DWASM_RT_NONCONFORMING_UNCHECKED_STACK_EXHAUSTION=1)
  host_includes=(-I"$deps/include" -I"$deps/build/_deps/rlbox-src/code/include"
                 -I"$wabt/wasm2c" -I"$wabt/third_party/simde" -I"$root/include")
}

port_source() {  # port_source NAME: clone the revision pinned in pins.json
  local name=$1 url revision
  read -r url revision < <(python3 -c "
import json,sys; s=json.load(open(sys.argv[1]))['sources'][sys.argv[2]]; print(s['url'], s['revision'])" \
    "$root/evaluation/coverage/pins.json" "$name")
  if [[ ! -d "$work/src-$name/.git" ]]; then
    git clone -q "$url" "$work/src-$name" || return 1
    git -C "$work/src-$name" checkout -q "$revision" || return 1
  fi
  [[ $(git -C "$work/src-$name" rev-parse HEAD) == "$revision" ]]
}

# port_module NAME IMPORTS_C -- CLANG_ARGS...
# Compiles the sources in CLANG_ARGS to $work/NAME/glue_lib_wasm2c.wasm, runs
# wasm2c and archives the module with the wasm2c runtime as $work/NAME/module.a.
# IMPORTS_C is the generated interspec_wasm_imports.c, or "-" for a module
# without tracking.
port_module() {
  local name=$1 imports=$2; shift 3
  local out="$work/$name"
  mkdir -p "$out"
  "$wasi/bin/clang" --sysroot "$wasi/share/wasi-sysroot" -O3 \
    -Wl,--export-all -Wl,--no-entry -Wl,--growable-table -Wl,--stack-first \
    -Wl,-z,stack-size=1048576 -Wl,--import-memory -Wl,--import-table \
    "$deps/c_src/wasm2c_sandbox_wrapper.c" "$@" -o "$out/glue_lib_wasm2c.wasm" || return 1
  "$wabt/build_release/wasm2c" -o "$out/glue_lib_wasm2c.c" "$out/glue_lib_wasm2c.wasm" || return 1
  local sources=("$out/glue_lib_wasm2c.c" "$wabt/wasm2c/wasm-rt-impl.c"
                 "$wabt/wasm2c/wasm-rt-mem-impl.c" "$deps/src/wasm2c_rt_minwasi.c"
                 "$deps/src/wasm2c_rt_mem.c")
  [[ $imports == - ]] || sources+=("$imports")
  local objects=() source obj
  for source in "${sources[@]}"; do
    obj="$out/$(basename "${source%.c}").o"
    cc -O2 -std=gnu11 "${host_defines[@]}" "${host_includes[@]}" -I"$out" \
      -c "$source" -o "$obj" || return 1
    objects+=("$obj")
  done
  rm -f "$out/module.a"
  ar rcs "$out/module.a" "${objects[@]}"
}

# port_host OUTPUT MODULE TRACKING CHECKS -- SOURCES_AND_FLAGS...
port_host() {
  local output=$1 module=$2 tracking=$3 checks=$4; shift 5
  g++ -std=c++17 -O2 "${host_defines[@]}" "${host_includes[@]}" -I"$work/$module" \
    -DINTERSPEC_TRACKING="$tracking" -DINTERSPEC_CHECKS="$checks" "$@" \
    "$work/$module/module.a" -pthread -ldl -lrt -lm -o "$output"
}
