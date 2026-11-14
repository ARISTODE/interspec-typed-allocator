#!/usr/bin/env bash
# Builds evaluation/memory/linear_memory_check.cpp against the module of the
# memcached/hash port (tracker item P9). WORK_DIR is a build directory of
# scripts/build_hash_port.sh.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${1:?usage: build_linear_memory_check.sh HASH_PORT_WORK_DIR}
source "$root/scripts/port_common.sh"
port_deps
test -f "$work/ordinary/module.a"
port_host "$work/bin/linear-memory-check" ordinary 0 0 -- \
  "$root/evaluation/memory/linear_memory_check.cpp"
