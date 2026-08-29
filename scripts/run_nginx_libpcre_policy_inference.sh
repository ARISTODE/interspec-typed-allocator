#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-nginx-libpcre-policy
pcre_src="$work/pcre"
revision=e67dabe61b327bd2d888954b0e74a7c9cfd0a195
rm -rf "$work"
mkdir -p "$work"

git clone -q https://github.com/nektro/pcre-8.45.git "$pcre_src"
git -C "$pcre_src" checkout -q "$revision"
cp "$root/integration/nginx_libpcre/interspec_trusted_uses.c" \
  "$pcre_src/interspec_trusted_uses.c"

codeql pack install "$root/analysis/ql"

cat > "$work/build.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$pcre_src"
cc -std=c11 -DHAVE_CONFIG_H -I. -c pcre_compile.c -o "$work/pcre_compile.o"
cc -std=c11 -DHAVE_CONFIG_H -I. -c interspec_trusted_uses.c -o "$work/interspec_trusted_uses.o"
EOF
chmod +x "$work/build.sh"

codeql database create "$work/db" \
  --language=cpp \
  --source-root="$pcre_src" \
  --command="$work/build.sh"

codeql query run \
  --database="$work/db" \
  --output="$work/policy.bqrs" \
  "$root/analysis/ql/nginx_libpcre_policy.ql"

codeql bqrs decode \
  --format=csv \
  --output="$work/policy.csv" \
  -- "$work/policy.bqrs"

cat "$work/policy.csv"

python3 "$root/tools/codeql_policy_to_json.py" \
  --csv "$work/policy.csv" \
  --output "$work/policy.json"

cat "$work/policy.json"
diff -u "$root/integration/nginx_libpcre/policy.json" "$work/policy.json"

echo "InterSpec P7c nginx/libpcre policy inference: generated policy matches checked-in policy"
