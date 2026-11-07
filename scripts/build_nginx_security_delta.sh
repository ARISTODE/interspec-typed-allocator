#!/usr/bin/env bash
# Dedicated sanitizer T builds with fault-only U. Never use for timing.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${INTERSPEC_NGINX_WORK:-${TMPDIR:-/tmp}/interspec-nginx-deployment}
jobs=${INTERSPEC_BUILD_JOBS:-2}
INTERSPEC_SECURITY_DELTA_BUILD=1 bash "$root/scripts/build_nginx_deployment.sh"

server="$work/server-security-asan"
mkdir -p "$server"
git -C "$work/upstream" archive 1be0fb0c9f9bc3489c7b40576efd6afe6b2eccd5 | tar -x -C "$server"
# The original build already applied the one-shot transformation to the
# generated PCRE source. Reapplying it would fail its asserted source guards.
# Reuse only the T-side nginx source edit for this new sanitized source tree.
cp "$work/server/src/core/ngx_regex.c" "$server/src/core/ngx_regex.c"
(cd "$server" && ./auto/configure --without-pcre2 --without-http_gzip_module \
  --with-cc-opt="-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -I$work/pcre" \
  --with-ld-opt="-fsanitize=address,undefined -L$work/native-pcre" \
  --prefix="$work/prefix-security-asan") > "$work/logs/security-configure.log" 2>&1
python3 - "$server/objs/Makefile" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1]); text = p.read_text()
assert text.count('-lpcre') == 1
p.write_text(text.replace('-lpcre', '$(INTERSPEC_BRIDGE) $(INTERSPEC_MODULE) '
                           '-lstdc++ -pthread -ldl -lrt -lm -fsanitize=address,undefined'))
PY

deps=${INTERSPEC_WASM_DEPS:-$work/wasm-deps}
wabt="$deps/build/_deps/wasm2c_compiler-src"
includes=(-I"$deps/include" -I"$deps/build/_deps/rlbox-src/code/include"
  -I"$wabt/wasm2c" -I"$wabt/third_party/simde" -I"$work/generated"
  -I"$root/include" -I"$work/pcre")
defines=(-DWASM_RT_USE_MMAP=1 -DWASM_RT_SKIP_SIGNAL_RECOVERY=1
  -DWASM_RT_NONCONFORMING_UNCHECKED_STACK_EXHAUSTION=1)

for variant in rlbox extended; do
  module=fault-ordinary
  flags=(-DINTERSPEC_TRACKING=0 -DINTERSPEC_CHECKS=0)
  if [[ $variant == extended ]]; then
    module=fault
    flags=(-DINTERSPEC_TRACKING=1 -DINTERSPEC_CHECKS=1)
  fi
  g++ -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
    -fno-sanitize-recover=all -DINTERSPEC_ENABLE_TRACE=1 \
    -DINTERSPEC_FAULT_TESTS=1 "${defines[@]}" "${flags[@]}" \
    "${includes[@]}" -I"$work/$module" \
    -c "$root/integration/nginx_server/bridge.cpp" \
    -o "$work/nginx-security-$variant-bridge.o"
  # All T objects were compiled with ASan/UBSan; only the bridge/module link
  # changes. Do not rebuild the source with an uninstrumented nginx variant.
  rm -f "$server/objs/nginx"
  make -C "$server" -j"$jobs" \
    INTERSPEC_BRIDGE="$work/nginx-security-$variant-bridge.o" \
    INTERSPEC_MODULE="$work/$module/module.a" \
    > "$work/logs/security-$variant-build.log" 2>&1
  cp "$server/objs/nginx" "$work/bin/nginx-security-$variant"
done

python3 - "$root" "$work" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path
root, work = map(Path, sys.argv[1:])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
result = {"schema": 1, "purpose": "H1 fault-only sanitizer comparator; no timing",
          "project_commit": subprocess.check_output(
              ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
          "binaries": {mode: sha(work / "bin" / f"nginx-security-{mode}")
                       for mode in ("rlbox", "extended")}}
(work / "security-delta-manifest.json").write_text(json.dumps(result, indent=2) + "\n")
PY
echo "Built H1 nginx sanitizer comparators"
