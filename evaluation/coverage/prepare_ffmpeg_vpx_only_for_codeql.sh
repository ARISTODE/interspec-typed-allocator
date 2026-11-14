#!/usr/bin/env bash
# Untraced preparation of the database ffmpeg_vpx_only (tracker item C2):
# remove the products of earlier builds so that the traced build compiles
# libvpx again and can build ffmpeg outside its source tree.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rm -rf "$root/build/libvpx-1.15.2-obj" "$root/build/libvpx-1.15.2" "$root/build/ffmpeg-vpx-only"
cd "$root/benchmarks/ffmpeg/ffmpeg-8.0"
[[ ! -f ffbuild/config.mak ]] || make distclean >/dev/null 2>&1 || true
