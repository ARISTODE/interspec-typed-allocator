#!/usr/bin/env bash
# Build step of scripts/run_tls_port.sh (tracker item I10). A separate script,
# run with errexit, so that any failing command fails the build.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${1:?usage: build_tls_port.sh WORK_DIR}
mkdir -p "$work"
source "$root/scripts/port_common.sh"
port_deps
port_source openssl_1_1_1w
ossl="$work/src-openssl_1_1_1w" dir="$root/integration/nginx_openssl"
jobs=${INTERSPEC_BUILD_JOBS:-2}

# OpenSSL for the sandbox, with the options of the artifact's build script
# (code/analysis/scripts/build_openssl_phase1_wasm_bridge.sh). One addition:
# openssl_wasi_compat.h is force-included, because WASI has no user ids.
if [[ ! -f "$work/ossl-wasm/libssl.a" ]]; then
  rm -rf "$work/ossl-wasm.tmp"
  cp -r "$ossl" "$work/ossl-wasm.tmp"
  (cd "$work/ossl-wasm.tmp" &&
   CC="$wasi/bin/clang --sysroot $wasi/share/wasi-sysroot" \
   AR="$wasi/bin/llvm-ar" RANLIB="$wasi/bin/llvm-ranlib" \
   ./Configure linux-generic32 no-shared no-threads no-asm no-tests no-ui-console \
     no-dso no-engine no-afalgeng no-devcryptoeng no-dynamic-engine no-async no-sock \
     no-stdio no-posix-io no-filenames --cross-compile-prefix='' --libdir=lib \
     -D_WASI_EMULATED_SIGNAL -D_WASI_EMULATED_MMAN -DNO_SYSLOG \
     -DOPENSSL_NO_SECURE_MEMORY -include "$dir/openssl_wasi_compat.h" \
     --openssldir="$work/ossl-wasm/install" &&
   make build_generated && make -j"$jobs" libcrypto.a libssl.a) > "$work/ossl-wasm.log" 2>&1
  mv "$work/ossl-wasm.tmp" "$work/ossl-wasm"
fi
# The same OpenSSL natively: the reference build of the shim, and the TLS
# client that every variant talks to.
if [[ ! -f "$work/ossl-native/libssl.a" ]]; then
  rm -rf "$work/ossl-native.tmp"
  cp -r "$ossl" "$work/ossl-native.tmp"
  (cd "$work/ossl-native.tmp" &&
   ./Configure linux-x86_64 no-shared no-tests no-dso no-engine \
     --openssldir="$work/ossl-native/install" &&
   make build_generated && make -j"$jobs" libcrypto.a libssl.a) > "$work/ossl-native.log" 2>&1
  mv "$work/ossl-native.tmp" "$work/ossl-native"
fi
echo "openssl $(git -C "$ossl" rev-parse HEAD)" > "$work/source-revisions.txt"

# The module: the artifact's shim, the glue and the two OpenSSL archives. There
# is no registry at this boundary (U returns no pointer), so one module serves
# both isolated variants; the test build adds the hooks.
flags=(-I"$dir" -I"$work/ossl-wasm/include" -D_WASI_EMULATED_SIGNAL -D_WASI_EMULATED_MMAN
       -Wl,-z,stack-size=4194304 -Wl,--initial-memory=33554432)
sources=("$dir/tls_u.c" "$dir/ossl_debug_stub.c"
         "$dir/tls_exdata.c"   # includes the artifact's shim, unchanged
         "$work/ossl-wasm/libssl.a" "$work/ossl-wasm/libcrypto.a"
         -lwasi-emulated-getpid -lwasi-emulated-mman -lwasi-emulated-signal)
port_module ordinary - -- "${flags[@]}" "${sources[@]}"
port_module fault - -- "${flags[@]}" -DINTERSPEC_FAULT_TESTS=1 "${sources[@]}"
if grep -q 'interspec_tls_poc\|interspec_tls_ex_fault' "$work/ordinary/glue_lib_wasm2c.h"; then
  echo 'Release module unexpectedly contains test hooks' >&2; exit 1
fi

mkdir -p "$work/bin" "$work/native"
native=(-I"$dir" -I"$work/ossl-native/include")
cc -O2 "${native[@]}" -c "$dir/tls_exdata.c" -o "$work/native/shim.o"
cc -O2 -c "$dir/ossl_debug_stub.c" -o "$work/native/stub.o"
g++ -std=c++17 -O2 "${native[@]}" "$dir/tls_native_bench.cpp" "$work/native/shim.o" \
  "$work/native/stub.o" \
  "$work/ossl-native/libssl.a" "$work/ossl-native/libcrypto.a" -pthread -ldl \
  -o "$work/bin/tls-native"
client=("$work/ossl-native/libssl.a" "$work/ossl-native/libcrypto.a")
port_host "$work/bin/tls-rlbox-only" ordinary 0 0 -- "${native[@]}" \
  "$dir/tls_app_bench.cpp" "${client[@]}"
port_host "$work/bin/tls-interspec" ordinary 0 1 -- "${native[@]}" \
  "$dir/tls_app_bench.cpp" "${client[@]}"
port_host "$work/bin/tls-interspec-fault" fault 0 1 -- "${native[@]}" \
  -DINTERSPEC_FAULT_TESTS=1 "$dir/tls_app_bench.cpp" "${client[@]}"
# For I6: the same test hooks without any InterSpec check.
port_host "$work/bin/tls-rlbox-only-fault" fault 0 0 -- "${native[@]}" \
  -DINTERSPEC_FAULT_TESTS=1 "$dir/tls_app_bench.cpp" "${client[@]}"
(cd "$work/bin" && sha256sum tls-*) > "$work/binaries.sha256"
