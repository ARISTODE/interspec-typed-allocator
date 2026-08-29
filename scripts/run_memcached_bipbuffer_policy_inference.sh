#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-memcached-bipbuffer-policy
memcached_src="$work/memcached"
revision=2d51e364799bc9698bd4b11728ea978cea12da6e
rm -rf "$work"
mkdir -p "$work"

git clone -q https://github.com/memcached/memcached.git "$memcached_src"
git -C "$memcached_src" checkout -q "$revision"
cp "$root/integration/memcached_bipbuffer/interspec_trusted_uses.c" \
  "$memcached_src/interspec_trusted_uses.c"

codeql pack install "$root/analysis/ql"

cat > "$work/build.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$memcached_src"
cc -std=c11 -I. -c bipbuffer.c -o "$work/bipbuffer.o"
cc -std=c11 -I. -c interspec_trusted_uses.c -o "$work/interspec_trusted_uses.o"
EOF
chmod +x "$work/build.sh"

codeql database create "$work/db" \
  --language=cpp \
  --source-root="$memcached_src" \
  --command="$work/build.sh"

codeql query run \
  --database="$work/db" \
  --output="$work/policy.bqrs" \
  "$root/analysis/ql/memcached_bipbuffer_policy.ql"

codeql bqrs decode \
  --format=csv \
  --output="$work/policy.csv" \
  -- "$work/policy.bqrs"

cat "$work/policy.csv"

python3 "$root/tools/codeql_policy_to_json.py" \
  --csv "$work/policy.csv" \
  --output "$work/policy.json"

cat "$work/policy.json"
diff -u "$root/integration/memcached_bipbuffer/policy.json" "$work/policy.json"

echo "InterSpec P7c memcached/bipbuffer policy inference: generated policy matches checked-in policy"
