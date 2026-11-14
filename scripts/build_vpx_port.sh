#!/usr/bin/env bash
# Build step of scripts/run_vpx_port.sh (tracker item I7). A separate script,
# run with errexit, so that any failing command fails the build.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${1:?usage: build_vpx_port.sh WORK_DIR}
mkdir -p "$work"
source "$root/scripts/port_common.sh"
port_deps
port_source libvpx
vpx="$work/src-libvpx" generated="$work/generated" dir="$root/integration/ffmpeg_libvpx"
jobs=${INTERSPEC_BUILD_JOBS:-2}

# libvpx with the artifact's configuration (scripts/build_libvpx_wasm_bridge.sh):
# the C-only target, one thread. -I untrusted/include supplies the artifact's
# setjmp.h, because WASI has no setjmp. PIC is disabled for the Wasm link. The
# native reference uses the same target, so that both run the same C code.
configure=(--target=generic-gnu --disable-examples --disable-tools --disable-unit-tests
           --disable-docs --disable-multithread --disable-runtime-cpu-detect
           --disable-shared --enable-static --enable-vp8 --enable-vp9)
if [[ ! -f "$work/vpx-wasm/libvpx.a" ]]; then
  mkdir -p "$work/vpx-wasm"
  (cd "$work/vpx-wasm" &&
   CC="$wasi/bin/clang --sysroot $wasi/share/wasi-sysroot" \
   CXX="$wasi/bin/clang++ --sysroot $wasi/share/wasi-sysroot" \
   LD="$wasi/bin/clang --sysroot $wasi/share/wasi-sysroot" \
   AR="$wasi/bin/llvm-ar" RANLIB="$wasi/bin/llvm-ranlib" NM="$wasi/bin/llvm-nm" \
   STRIP="$wasi/bin/llvm-strip" \
   CFLAGS="-O3 -I$dir/untrusted/include" CXXFLAGS="-O3 -I$dir/untrusted/include" \
   "$vpx/configure" "${configure[@]}" --disable-pic --disable-webm-io --disable-libyuv &&
   make -j"$jobs" libvpx.a)
fi
if [[ ! -f "$work/vpx-native/libvpx.a" ]]; then
  mkdir -p "$work/vpx-native"
  (cd "$work/vpx-native" &&
   CFLAGS="-O3" CXXFLAGS="-O3" "$vpx/configure" "${configure[@]}" --disable-webm-io \
     --disable-libyuv &&
   make -j"$jobs" libvpx.a)
fi

python3 "$root/tools/generate_wasm_boundary_policy.py" \
  --policy "$dir/policy.json" --boundary "$dir/boundary.json" \
  --source "$dir/vpx_u.c" --out-dir "$generated" \
  --namespace 'interspec::ffmpeg_libvpx_generated' --site-id-base 0x00800000
cp "$generated/interspec_u_policy.h" "$generated/interspec_vpx_u_policy.h"
cp "$generated/interspec_t_policy.h" "$generated/interspec_vpx_t_policy.h"

# The registry learns the two kinds of buffer that T reads at their allocation
# sites in libvpx: the VP8 frame buffers (vpx_scale/generic/yv12config.c) and
# the encoder's output buffer (vp8/vp8_cx_iface.c). Each replacement must match
# exactly once. The patched copies are linked ahead of libvpx.a, so the
# archive's own members of the same name are not used.
python3 - "$vpx" "$generated" <<'PY'
import sys
from pathlib import Path
vpx, out = Path(sys.argv[1]), Path(sys.argv[2])
def patch(relative, name, pairs):
    text = (vpx / relative).read_text()
    for old, new in pairs:
        if text.count(old) != 1:
            sys.exit(f"{relative}: expected exactly one occurrence of {old!r}")
        text = text.replace(old, new)
    (out / name).write_text(text)
patch("vpx_scale/generic/yv12config.c", "yv12config.c", [
    # vp8_yv12_alloc_frame_buffer
    ("      ybf->buffer_alloc = (uint8_t *)vpx_memalign(32, frame_size);\n",
     "      ybf->buffer_alloc =\n"
     "          (uint8_t *)(uintptr_t)INTERSPEC_SITE_FRAME_BUFFER_ALLOC(frame_size);\n"),
    # vp8_yv12_de_alloc_frame_buffer
    ("int vp8_yv12_de_alloc_frame_buffer(YV12_BUFFER_CONFIG *ybf) {\n"
     "  if (ybf) {\n"
     "    // If libvpx is using frame buffer callbacks then buffer_alloc_sz must\n"
     "    // not be set.\n"
     "    if (ybf->buffer_alloc_sz > 0) {\n"
     "      vpx_free(ybf->buffer_alloc);\n",
     "int vp8_yv12_de_alloc_frame_buffer(YV12_BUFFER_CONFIG *ybf) {\n"
     "  if (ybf) {\n"
     "    // If libvpx is using frame buffer callbacks then buffer_alloc_sz must\n"
     "    // not be set.\n"
     "    if (ybf->buffer_alloc_sz > 0) {\n"
     "      if (ybf->buffer_alloc)\n"
     "        (void)interspec_wasm_release((uint32_t)(uintptr_t)ybf->buffer_alloc);\n"),
])
patch("vp8/vp8_cx_iface.c", "vp8_cx_iface.c", [
    ("    priv->cx_data = malloc(priv->cx_data_sz);\n",
     "    priv->cx_data =\n"
     "        (unsigned char *)(uintptr_t)INTERSPEC_SITE_CX_DATA_ALLOC(priv->cx_data_sz);\n"),
    ("  free(ctx->cx_data);\n  vp8_remove_compressor(&ctx->cpi);\n",
     "  if (ctx->cx_data) (void)interspec_wasm_release((uint32_t)(uintptr_t)ctx->cx_data);\n"
     "  vp8_remove_compressor(&ctx->cpi);\n"),
])
PY

flags=(-DNDEBUG -I"$dir" -I"$dir/untrusted/include" -I"$vpx" -I"$generated"
       -Wl,-z,stack-size=4194304)
tracked=(-DINTERSPEC_TRACKING=1 -I"$work/vpx-wasm" -I"$vpx/vp8"
         -include "$generated/interspec_vpx_u_policy.h"
         "$generated/yv12config.c" "$generated/vp8_cx_iface.c")
port_module ordinary - -- "${flags[@]}" -DINTERSPEC_TRACKING=0 \
  "$dir/vpx_u.c" "$dir/untrusted/libvpx_shim.c" "$work/vpx-wasm/libvpx.a"
port_module typed "$generated/interspec_wasm_imports.c" -- "${flags[@]}" "${tracked[@]}" \
  "$dir/vpx_u.c" "$dir/untrusted/libvpx_shim.c" "$work/vpx-wasm/libvpx.a"
port_module fault "$generated/interspec_wasm_imports.c" -- "${flags[@]}" "${tracked[@]}" \
  -DINTERSPEC_FAULT_TESTS=1 \
  "$dir/vpx_u.c" "$dir/untrusted/libvpx_shim.c" "$work/vpx-wasm/libvpx.a"
if grep -q 'interspecWasm' "$work/ordinary/glue_lib_wasm2c.h"; then
  echo 'RLBox-only module unexpectedly imports typed allocation' >&2; exit 1
fi
if grep -q 'interspec_vpx_fault\|interspec_vpx_poc' "$work/typed/glue_lib_wasm2c.h"; then
  echo 'Release module unexpectedly contains test hooks' >&2; exit 1
fi

mkdir -p "$work/bin"
g++ -std=c++17 -O2 -I"$vpx" -I"$dir" "$dir/vpx_native_bench.cpp" \
  "$work/vpx-native/libvpx.a" -lm -o "$work/bin/vpx-native"
host=(-I"$vpx" -I"$dir")
port_host "$work/bin/vpx-rlbox-only" ordinary 0 0 -- "${host[@]}" "$dir/vpx_app_bench.cpp"
port_host "$work/bin/vpx-tracked-no-check" typed 1 0 -- "${host[@]}" -I"$generated" \
  "$dir/vpx_app_bench.cpp"
port_host "$work/bin/vpx-interspec" typed 1 1 -- "${host[@]}" -I"$generated" \
  "$dir/vpx_app_bench.cpp"
port_host "$work/bin/vpx-interspec-fault" fault 1 1 -- "${host[@]}" -I"$generated" \
  -DINTERSPEC_FAULT_TESTS=1 "$dir/vpx_app_bench.cpp"
(cd "$work/bin" && sha256sum vpx-*) > "$work/binaries.sha256"
echo "libvpx $(git -C "$vpx" rev-parse HEAD)" > "$work/source-revisions.txt"
