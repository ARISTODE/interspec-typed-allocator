#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/p9c-results"}

rm -rf "$out"
mkdir -p "$out"

python3 "$root/tools/build_p9c_report.py" \
  --output-dir "$out" \
  --require-source-integrity

python3 "$root/tools/render_p9c_results.py" \
  --report "$out/p9c-report.json" \
  --cases "$out/p9c-cases.csv" \
  --output "$out/P9C_RESULTS.md"

cp "$root/evaluation/p9c/interspec_paper_integrity_coverage.csv" \
  "$out/interspec_paper_integrity_coverage.csv"
cp "$root/evaluation/p9c/paper_sp3_manifest.json" \
  "$out/paper_sp3_manifest.json"

{
  echo "commit=$(git -C "$root" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "paper_artifact_commit=2b2d2fd4de69ee44a4363e69f8cfb82ceed132db"
  echo "paper_coverage_blob=5c5f0e9b4b4a5b548504653680d0cf158d2db613"
  echo "python=$(python3 --version 2>&1)"
} > "$out/environment.txt"

cat > "$out/README.txt" <<'EOF'
P9c reconciles Extended SP3 coverage with the final InterSpec paper's field-level
SP3 counts.

p9c-report.json records source integrity, capability-resolution status, and
prototype mapping status.
p9c-cases.csv contains exactly 32 stable paper count-unit identifiers.
P9C_RESULTS.md is mechanically rendered from those machine-readable artifacts.

The current source snapshot preserves the final paper's aggregate field counts,
but not a declared one-row-per-paper-field identity map. Matching cardinality in
a raw report is not treated as proof of identity. Cases without reconstructed
identity remain explicitly classified as insufficient_source_metadata.
EOF

echo "P9c coverage results written to $out"
