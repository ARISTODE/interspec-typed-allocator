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
"$root/scripts/write_p8_rlbox_environment.sh" "$out/environment.txt"
reference_commit=$(git -C "$root" rev-parse HEAD 2>/dev/null || echo unknown)
python3 "$root/tools/render_p9a_results.py" \
  --summary "$out/rsync-performance-summary.csv" \
  --commit "$reference_commit" \
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
