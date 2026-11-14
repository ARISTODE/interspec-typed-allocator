#!/usr/bin/env bash
# CodeQL build command for the database ffmpeg_vpx_only (tracker item C2):
# libvpx 1.15.2 exactly as in build_ffmpeg_for_codeql.sh, and ffmpeg 8.0
# configured with only the components a VP8/VP9 transcode through libvpx uses.
# In the full database only libavcodec/libvpxenc.c and libavcodec/libvpxdec.c
# call libvpx or access a field of one of its types
# (evaluation/results/tracker/C2/09: ffmpeg-files-using-libvpx.csv); both are
# compiled here. The full database has 27,510 ffmpeg functions, and the
# queries did not finish on it.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
vpx="$root/benchmarks/libvpx/libvpx-1.15.2"
prefix="$root/build/libvpx-1.15.2"
mkdir -p "$root/build/libvpx-1.15.2-obj" "$prefix"
cd "$root/build/libvpx-1.15.2-obj"
"$vpx/configure" --prefix="$prefix" --disable-examples --disable-tools --disable-docs \
  --disable-unit-tests --enable-vp8 --enable-vp9 --disable-shared --enable-static
make -j"$(nproc)"
make install
mkdir -p "$root/build/ffmpeg-vpx-only"
cd "$root/build/ffmpeg-vpx-only"
PKG_CONFIG_PATH="$prefix/lib/pkgconfig" "$root/benchmarks/ffmpeg/ffmpeg-8.0/configure" \
  --disable-everything --disable-autodetect --enable-libvpx \
  --enable-encoder=libvpx_vp8,libvpx_vp9,rawvideo \
  --enable-decoder=libvpx_vp8,libvpx_vp9,rawvideo \
  --enable-demuxer=ivf,matroska,yuv4mpegpipe,rawvideo \
  --enable-muxer=ivf,webm,yuv4mpegpipe,rawvideo \
  --enable-parser=vp8,vp9 --enable-protocol=file,pipe \
  --enable-filter=scale,format,null \
  --disable-doc --disable-x86asm \
  --extra-cflags="-I$prefix/include" --extra-ldflags="-L$prefix/lib"
make -j"$(nproc)"
