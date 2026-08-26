#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-rsync-popt-policy
rsync_src="$work/rsync"
rm -rf "$work"
mkdir -p "$work"

git clone -q https://github.com/RsyncProject/rsync.git "$rsync_src"
git -C "$rsync_src" checkout -q 7c20b077c980036a19587701cec320cc88e42a4a

codeql pack install "$root/analysis/ql"

cat > "$work/build.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$rsync_src"
./configure \
  --with-included-popt \
  --disable-md2man \
  --disable-xxhash \
  --disable-zstd \
  --disable-lz4 \
  --disable-openssl \
  --disable-roll-simd
make -j2 options.o popt/popt.o
EOF
chmod +x "$work/build.sh"

codeql database create "$work/db" \
  --language=cpp \
  --source-root="$rsync_src" \
  --command="$work/build.sh"

codeql query run \
  --database="$work/db" \
  --output="$work/policy.bqrs" \
  "$root/analysis/ql/rsync_popt_policy.ql"

codeql bqrs decode \
  --format=csv \
  --output="$work/policy.csv" \
  -- "$work/policy.bqrs"

cat "$work/policy.csv"

python3 "$root/tools/codeql_policy_to_json.py" \
  --csv "$work/policy.csv" \
  --output "$work/policy.json"

cat "$work/policy.json"
diff -u "$root/integration/rsync_popt/policy.json" "$work/policy.json"

echo "InterSpec P4 rsync/popt policy inference: generated policy matches checked-in policy"
