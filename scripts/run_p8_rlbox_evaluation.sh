#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/p8-rlbox-results"}
rm -rf "$out"
mkdir -p "$out"

base_log="$out/rlbox-base.log"
yaml_log="$out/yaml-extension.log"

if ! "$root/scripts/run_rlbox_nacl_poc.sh" >"$base_log" 2>&1; then
  echo "RLBox NaCl / P4c / P7c base integration or P8 app benchmark failed" >&2
  tail -n 300 "$base_log" >&2
  exit 1
fi

if ! "$root/scripts/run_yaml_libyaml_rlbox_extension.sh" >"$yaml_log" 2>&1; then
  echo "P7c/P8 yaml + boundary measurement extension failed" >&2
  tail -n 300 "$yaml_log" >&2
  exit 1
fi

boundary_raw=/tmp/interspec-p8-boundary-performance.csv
app_raw=/tmp/interspec-p8-rsync-performance.csv
boundary_bench_log=/tmp/interspec-p8-boundary-bench.log

test -s "$boundary_raw"
test -s "$app_raw"

cp "$boundary_raw" "$out/boundary-performance.csv"
cp "$app_raw" "$out/rsync-performance.csv"
if [[ -s "$boundary_bench_log" ]]; then
  cp "$boundary_bench_log" "$out/boundary-bench.log"
fi

python3 "$root/tools/summarize_p8_performance.py" \
  --input "$out/boundary-performance.csv" \
  --output "$out/boundary-performance-summary.csv"
python3 "$root/tools/summarize_p8_application.py" \
  --input "$out/rsync-performance.csv" \
  --output "$out/rsync-performance-summary.csv"

"$root/scripts/write_p8_rlbox_environment.sh" "$out/environment.txt"

cat > "$out/README.txt" <<'EOF'
P8 RLBox performance evidence

boundary-performance.csv
  Paired trusted-use measurements over real valid U objects.

rsync-performance.csv
  Paired complete-rsync process measurements.

In both datasets:
  tracked_no_check retains sandboxing, typed allocation/provenance, and
  marshalling, but bypasses final T-side Extended-SP3 pointer acceptance.
  extended_sp3 performs the normal security validation.

Therefore the reported percentage is incremental validation overhead, not total
Extended-SP3 overhead relative to plain RLBox.

Hosted CI measurements are a reproducible reference only. Regenerate this
folder on controlled hardware for publication performance numbers.
EOF

cat "$out/boundary-performance-summary.csv"
cat "$out/rsync-performance-summary.csv"
echo "P8 RLBox evaluation results written to $out"
