#!/usr/bin/env bash
# CodeQL build command for ffmpeg 8.0 with libvpx 1.15.2 (tracker item C1).
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
cd "$root/benchmarks/ffmpeg/ffmpeg-8.0"
PKG_CONFIG_PATH="$prefix/lib/pkgconfig" ./configure --enable-libvpx --disable-doc \
  --disable-x86asm --extra-cflags="-I$prefix/include" --extra-ldflags="-L$prefix/lib"
make -j"$(nproc)"
