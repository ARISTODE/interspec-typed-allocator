#!/usr/bin/env bash
# CodeQL build command for the magick/libpng boundary (tracker item C1).
# The artifact's build script expects pnglibconf.h.prebuilt next to the libpng
# sources; upstream libpng keeps it under scripts/. Copy it, then run the
# artifact's script unchanged.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cp "$root/third_party/libpng/scripts/pnglibconf.h.prebuilt" \
   "$root/third_party/libpng/pnglibconf.h.prebuilt"
bash "$root/scripts/build_codeql_magick_libpng.sh"
