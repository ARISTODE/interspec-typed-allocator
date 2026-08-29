#!/usr/bin/env bash
set -euo pipefail

# Keep the large pinned RLBox/NaCl integration recipe in a mechanically stable
# implementation file. This front-end supplies source-project preparation that
# must happen immediately after an upstream checkout, before that implementation
# configures the combined NaCl build.
script_dir=$(cd "$(dirname "$0")" && pwd)
impl="$script_dir/run_rlbox_nacl_poc_impl.sh"
git_bin=$(type -P git)

# PCRE1 keeps config.h as a template in the source tree. A normal CMake build
# generates a configured config.h containing LINK_SIZE and the other internal
# constants. The NaCl integration compiles the real PCRE C sources directly, so
# reproduce that normal configuration step after the exact pinned checkout.
git()
{
  "$git_bin" "$@"
  local status=$?
  if [[ $status -eq 0 && $# -ge 5 && "$1" == "-C" &&
        "$3" == "checkout" && "$4" == "-q" &&
        "$5" == "e67dabe61b327bd2d888954b0e74a7c9cfd0a195" &&
        "$2" == */c_src/pcre-src ]]; then
    local pcre_src="$2"
    local pcre_config="${TMPDIR:-/tmp}/interspec-pcre-config"
    rm -rf "$pcre_config"
    cmake -S "$pcre_src" -B "$pcre_config" \
      -DBUILD_SHARED_LIBS=OFF \
      -DPCRE_BUILD_PCRE8=ON \
      -DPCRE_BUILD_PCRE16=OFF \
      -DPCRE_BUILD_PCRE32=OFF \
      -DPCRE_BUILD_PCRECPP=OFF \
      -DPCRE_BUILD_PCREGREP=OFF \
      -DPCRE_BUILD_TESTS=OFF \
      -DPCRE_SUPPORT_JIT=OFF \
      -DPCRE_SUPPORT_UTF=OFF \
      -DPCRE_SUPPORT_UNICODE_PROPERTIES=OFF \
      -DPCRE_SHOW_REPORT=OFF >/dev/null
    test -s "$pcre_config/config.h"
    cp "$pcre_config/config.h" "$pcre_src/config.h"
  fi
  return $status
}

# The integration recipe predates the explicit non-JIT PCRE configuration and
# listed pcre_jit_compile.c unconditionally. That source embeds SLJIT directly;
# it is neither built nor required when PCRE_SUPPORT_JIT=OFF. Produce a temporary
# copy of the otherwise stable recipe with exactly those two CMake-list entries
# removed (source list + per-source compile-definition list).
filtered_impl=$(mktemp "${TMPDIR:-/tmp}/interspec-rlbox-nacl-impl.XXXXXX")
trap 'rm -f "$filtered_impl"' EXIT
python3 - "$impl" "$filtered_impl" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text()
needle = '    "               ${CMAKE_SOURCE_DIR}/pcre-src/pcre_jit_compile.c\\n"\n'
count = source.count(needle)
if count != 2:
    raise SystemExit(f"expected exactly two PCRE JIT source-list entries, found {count}")
Path(sys.argv[2]).write_text(source.replace(needle, ""))
PY

# Source rather than exec so the git() preparation hook remains visible to the
# integration recipe. $0 still names this front-end, preserving its root lookup.
source "$filtered_impl"
