#!/usr/bin/env bash
# CodeQL build command for rsync with its bundled popt (tracker item C1).
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root/benchmarks/rsync"
./configure --with-included-popt --disable-md2man --disable-xxhash --disable-zstd \
  --disable-lz4 --disable-openssl --disable-idn --disable-roll-simd \
  --disable-roll-asm --disable-md5-asm
make clean
make -j"$(nproc)" rsync
