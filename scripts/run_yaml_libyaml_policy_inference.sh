#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-yaml-libyaml-policy
yaml_src="$work/libyaml"
revision=90a56d4500aa1a1798514c5cb55c3ad4cb095f94
rm -rf "$work"
mkdir -p "$work"

git clone -q https://github.com/yaml/libyaml.git "$yaml_src"
git -C "$yaml_src" checkout -q "$revision"
cp "$root/integration/yaml_libyaml/interspec_trusted_uses.c" \
  "$yaml_src/interspec_trusted_uses.c"

# libyaml normally generates config.h through CMake/autoconf. The policy build
# compiles only the source needed by CodeQL, so reproduce the version-only
# generated header from cmake/config.h.in directly.
cat > "$yaml_src/src/config.h" <<'EOF'
#define YAML_VERSION_MAJOR 0
#define YAML_VERSION_MINOR 2
#define YAML_VERSION_PATCH 5
#define YAML_VERSION_STRING "0.2.5"
EOF

codeql pack install "$root/analysis/ql"

cat > "$work/build.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$yaml_src"
cc -std=c11 -DHAVE_CONFIG_H=1 -Iinclude -Isrc -c src/api.c -o "$work/api.o"
cc -std=c11 -Iinclude -Isrc -c interspec_trusted_uses.c -o "$work/interspec_trusted_uses.o"
EOF
chmod +x "$work/build.sh"

codeql database create "$work/db" \
  --language=cpp \
  --source-root="$yaml_src" \
  --command="$work/build.sh"

codeql query run \
  --database="$work/db" \
  --output="$work/policy.bqrs" \
  "$root/analysis/ql/yaml_libyaml_policy.ql"

codeql bqrs decode \
  --format=csv \
  --output="$work/policy.csv" \
  -- "$work/policy.bqrs"

cat "$work/policy.csv"

python3 "$root/tools/codeql_policy_to_json.py" \
  --csv "$work/policy.csv" \
  --output "$work/policy.json"

cat "$work/policy.json"
diff -u "$root/integration/yaml_libyaml/policy.json" "$work/policy.json"

echo "InterSpec P7c yaml/libyaml policy inference: generated policy matches checked-in policy"
