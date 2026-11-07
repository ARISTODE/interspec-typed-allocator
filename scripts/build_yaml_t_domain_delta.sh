#!/usr/bin/env bash
# Native libyaml read-handler API plus actual RLBox U-domain predicate.
# The modeled malicious pointer is injected in project-authored T code.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${INTERSPEC_MEMCACHED_WORK:-${TMPDIR:-/tmp}/interspec-memcached-deployment}
deps=${INTERSPEC_WASM_DEPS:-$work/wasm-deps}
yaml="$work/security-asan/libyaml"
revision=90a56d4500aa1a1798514c5cb55c3ad4cb095f94
mkdir -p "$work/security-asan/yaml-objects"
if [[ ! -d "$yaml/.git" ]]; then
  git clone -q https://github.com/yaml/libyaml.git "$yaml"
  git -C "$yaml" checkout -q "$revision"
fi
[[ $(git -C "$yaml" rev-parse HEAD) == "$revision" ]]
python3 - "$yaml" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
config = ("#define YAML_VERSION_MAJOR 0\n#define YAML_VERSION_MINOR 2\n"
          "#define YAML_VERSION_PATCH 5\n#define YAML_VERSION_STRING \"0.2.5\"\n")
(root / "include/config.h").write_text(config)
(root / "src/config.h").write_text(config)
PY
for source in "$yaml"/src/*.c; do
  object="$work/security-asan/yaml-objects/$(basename "${source%.c}").o"
  cc -std=gnu11 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
    -DHAVE_CONFIG_H=1 -I"$yaml/include" -I"$yaml/src" -c "$source" -o "$object"
done
ar rcs "$work/security-asan/libyaml-native.a" "$work/security-asan/yaml-objects"/*.o
wabt="$deps/build/_deps/wasm2c_compiler-src"
g++ -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -I"$deps/include" -I"$deps/build/_deps/rlbox-src/code/include" \
  -I"$wabt/wasm2c" -I"$wabt/third_party/simde" \
  -I"$work/ordinary" -I"$root/include" -I"$yaml/include" \
  "$root/integration/yaml_libyaml/yaml_t_domain_delta.cpp" \
  "$work/security-asan/libyaml-native.a" "$work/ordinary/module.a" \
  -pthread -ldl -lrt -lm -o "$work/bin/yaml-t-domain-delta"
echo "Built project-authored libyaml T-domain security-delta driver"
