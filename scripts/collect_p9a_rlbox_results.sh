#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/p9a-rlbox-results"}
raw=/tmp/interspec-p9a-rsync-performance.csv

rm -rf "$out"
mkdir -p "$out"
test -s "$raw"
cp "$raw" "$out/rsync-performance.csv"
python3 "$root/tools/summarize_p9a_application.py" \
  --input "$out/rsync-performance.csv" \
  --output "$out/rsync-performance-summary.csv"

commit=${GITHUB_SHA:-}
if [[ -z "$commit" ]]; then
  commit=$(git -C "$root" rev-parse HEAD 2>/dev/null || true)
fi
if [[ -z "$commit" ]]; then
  commit=unknown
fi
cpu=$(awk -F: '/^model name[[:space:]]*:/ {sub(/^[[:space:]]+/, "", $2); print $2; exit}' /proc/cpuinfo 2>/dev/null || true)
if [[ -z "$cpu" ]]; then
  cpu=unknown
fi
{
  echo "commit=$commit"
  echo "kernel=$(uname -srmo)"
  echo "cpu=$cpu"
  echo "application_repetitions=${INTERSPEC_P9A_APP_REPETITIONS:-${INTERSPEC_P8_APP_REPETITIONS:-9}}"
  echo "rlbox_baseline=rlbox_only"
  echo "tracking_configuration=tracked_no_check"
  echo "security_configuration=extended_sp3"
  echo "note=rlbox_only disables the active InterSpec typed-allocation/provenance runtime path and final Extended-SP3 validation for the measured rsync/popt boundary"
} > "$out/environment.txt"

python3 "$root/tools/render_p9a_results.py" \
  --summary "$out/rsync-performance-summary.csv" \
  --commit "$commit" \
  --environment "$out/environment.txt" \
  --output "$out/P9A_RESULTS.md"

cat > "$out/README.txt" <<'EOF'
P9a RLBox-only baseline evidence

rsync-performance.csv
  Three-way raw samples for rlbox_only, tracked_no_check, and extended_sp3.

rsync-performance-summary.csv
  Paired decomposition of tracking/provenance overhead, final validation
  overhead, and total Extended-SP3 overhead over the RLBox-only runtime path.

P9A_RESULTS.md
  Mechanically rendered paper-facing reference table.

Baseline semantics
  rlbox_only keeps the pinned RLBox + NaCl sandbox and the same trusted rsync
  popt API bridge shape, but uses the pinned uninstrumented popt.c and ordinary
  sandbox allocation. The trusted bridge does not reserve the typed arena,
  instantiate PolicyRuntime, register allocation/lifetime callbacks, or execute
  Extended-SP3 acceptance checks.

The same patched NaCl backend binary contains dormant InterSpec support code in
all modes. No typed arena or InterSpec callbacks are activated by rlbox_only.
P9b will move the final paper evaluation to the wasm2c backend.
EOF

cat "$out/rsync-performance-summary.csv"
echo "P9a RLBox-only baseline results written to $out"
