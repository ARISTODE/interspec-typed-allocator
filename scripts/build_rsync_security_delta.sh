#!/usr/bin/env bash
# Two real rsync/popt wasm2c builds: untracked RLBox and Extended SP3.
# Fault-only T executables are fully ASan/UBSan-instrumented, never timed.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-rlbox-wasm2c
revision=7c20b077c980036a19587701cec320cc88e42a4a

INTERSPEC_FAULT_TESTS=1 bash "$root/scripts/run_rlbox_wasm2c_poc.sh"
module=$(find "$work/build" -name libglue_lib_imported.a -print -quit)
[[ -f "$module" ]]
cp "$module" "$work/rsync-typed-fault-module.a"

# Source input is pinned upstream popt, not the generated typed-site rewrite.
# Both variants retain the identical shadow-slot and copyback bridge.
popt="$work/c_src/rsync-popt"
git -C "$work/rsync-src" show "$revision:popt/popt.c" > "$popt/popt.c"
python3 - "$popt/popt.c" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1]); text = p.read_text()
needle = '#include "system.h"\n'
assert text.count(needle) == 1
p.write_text(text.replace(needle, needle + '#include <stdint.h>\n'
                          '#include "interspec_popt_u_policy.h"\n'
                          '#include "p9b_wasi_compat.h"\n', 1))
PY
python3 - "$work/CMakeLists.txt" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1]); text = p.read_text()
needle = '                            -DINTERSPEC_TYPED_POPT=1\n'
assert text.count(needle) == 2
p.write_text(text.replace(needle, needle +
                          '                            -DINTERSPEC_RLBOX_SECURITY_COMPARATOR=1\n'))
PY
cmake -S "$work" -B "$work/build" -DCMAKE_BUILD_TYPE=Release \
  > "$work/security-baseline-configure.log" 2>&1
cmake --build "$work/build" --target glue_lib_imported --parallel 2 \
  > "$work/security-baseline-build.log" 2>&1
cp "$module" "$work/rsync-rlbox-fault-module.a"
if grep -q 'interspecWasm' "$work/build/wasm_imported/glue_lib_wasm2c.h"; then
  echo "RLBox comparator unexpectedly imports trusted allocation metadata" >&2
  exit 1
fi

common_includes=(-I"$work/include" -I"$work/build/_deps/rlbox-src/code/include"
  -I"$work/build/_deps/wasm2c_compiler-src/wasm2c"
  -I"$work/build/_deps/wasm2c_compiler-src/third_party/simde"
  -I"$work/build/wasm_imported" -I"$root/include"
  -I"$work/interspec-popt-generated" -I"$work/rsync-src/popt")

# The two modules export the same ABI, so rebuilding the generated host bridge
# with one preprocessor switch is sufficient to compare them.
for variant in rlbox extended; do
  flag=()
  if [[ $variant == rlbox ]]; then flag=(-DINTERSPEC_RLBOX_SECURITY_COMPARATOR=1); fi
  g++ -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
    -fno-sanitize-recover=all -DINTERSPEC_FAULT_TESTS=1 "${flag[@]}" \
    "${common_includes[@]}" \
    -c "$work/p9b_wasm_bridge.cpp" -o "$work/rsync-security-$variant-bridge.o"
done

trusted="$work/rsync-security-asan"
if [[ ! -d "$trusted/.git" ]]; then
  git -C "$work/rsync-src" worktree add --detach "$trusted" "$revision"
fi
[[ $(git -C "$trusted" rev-parse HEAD) == "$revision" ]]
if [[ ! -f "$trusted/Makefile" ]]; then
  (cd "$trusted" && ./configure --disable-md2man --disable-xxhash \
    --disable-zstd --disable-lz4 --disable-openssl --disable-idn \
    --disable-roll-simd --disable-roll-asm --disable-md5-asm \
    CFLAGS='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer' \
    LDFLAGS='-fsanitize=address,undefined') \
    > "$work/security-rsync-configure.log" 2>&1
fi
python3 - "$trusted/Makefile" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1]); s = p.read_text()
old = '$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJS) $(LIBS)'
new = '$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJS) $(P4C_BRIDGE) $(LIBS) $(P4C_LIBS)'
if new not in s:
    assert s.count(old) == 1
    p.write_text(s.replace(old, new, 1))
PY
for variant in extended rlbox; do
  module="$work/rsync-$variant-fault-module.a"
  bridge="$work/rsync-security-$variant-bridge.o"
  # The second build relinks the same sanitizer-instrumented T objects.
  rm -f "$trusted/rsync"
  make -C "$trusted" -j2 rsync P4C_BRIDGE="$bridge" \
    P4C_LIBS="$module -lstdc++ -pthread -ldl -lrt -lm -fsanitize=address,undefined" \
    > "$work/security-rsync-$variant-build.log" 2>&1
  cp "$trusted/rsync" "$work/rsync-security-$variant"
  g++ -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
    -fno-sanitize-recover=all "$root/integration/rsync_popt/copyback_canary.cpp" \
    "$bridge" "${common_includes[@]}" "$module" \
    -pthread -ldl -lrt -lm -o "$work/copyback-security-$variant"
done

python3 - "$root" "$work" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path
root, work = map(Path, sys.argv[1:])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
result = {"schema": 1, "purpose": "H1 rsync/popt fault-only sanitizer comparison",
          "project_commit": subprocess.check_output(
              ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
          "binary_sha256": {mode: sha(work / f"rsync-security-{mode}")
                            for mode in ("rlbox", "extended")},
          "copyback_sha256": {mode: sha(work / f"copyback-security-{mode}")
                              for mode in ("rlbox", "extended")},
          "timing_permitted": False}
(work / "security-delta-manifest.json").write_text(json.dumps(result, indent=2) + "\n")
PY
echo "Built H1 rsync/popt sanitizer comparators"
