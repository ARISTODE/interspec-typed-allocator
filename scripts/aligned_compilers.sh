#!/usr/bin/env bash
# Usage: aligned_compilers.sh DIR
#
# Writes wrappers for cc, gcc, g++ and c++ into DIR. Each wrapper runs the
# compiler of the same name found on the current PATH and adds
# -falign-functions=64. Put DIR first on PATH before a build script to get
# binaries in which every function that the compiler aligns starts on a
# 64-byte boundary:
#
#   export PATH="$(bash scripts/aligned_compilers.sh /tmp/aligned-cc):$PATH"
#
# Why: the time of a sandboxed library depends on where the linker puts its
# hot loops relative to 64-byte boundaries, and that position changes with the
# size of the code linked before it. The trusted side of the RLBox-only and the
# InterSpec configuration differs in size, so without a fixed alignment the two
# configurations run the same library code at different positions. The
# measurement in evaluation/results/tracker/R3/02-code-placement shows a 13%
# difference between two links of one program that differ by 32 bytes of
# padding. tools/check_function_alignment.py checks the result.
set -euo pipefail
dir=${1:?usage: aligned_compilers.sh DIR}
mkdir -p "$dir"
dir=$(cd "$dir" && pwd)
clean_path=$(printf '%s' "$PATH" | tr ':' '\n' | grep -vxF "$dir" | paste -sd: -)
for name in cc gcc g++ c++; do
  real=$(PATH="$clean_path" command -v "$name") || { echo "aligned_compilers.sh: no $name on PATH" >&2; exit 1; }
  printf '#!/bin/sh\nexec %s "$@" -falign-functions=64\n' "$real" > "$dir/$name"
  chmod +x "$dir/$name"
done
echo "$dir"
