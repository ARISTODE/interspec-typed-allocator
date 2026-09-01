#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/p9c-results"}

rm -rf "$out"
mkdir -p "$out"

python3 "$root/tools/build_p9c_report.py" \
  --output-dir "$out" \
  --require-source-integrity \
  --require-complete

python3 "$root/tools/render_p9c_results.py" \
  --report "$out/p9c-report.json" \
  --cases "$out/p9c-cases.csv" \
  --output "$out/P9C_RESULTS.md"

cp "$root/evaluation/p9c/interspec_paper_integrity_coverage.csv" \
  "$out/interspec_paper_integrity_coverage.csv"
cp "$root/evaluation/p9c/paper_sp3_manifest.json" \
  "$out/paper_sp3_manifest.json"
cp "$root/evaluation/p9c/source_reconstruction_audit.json" \
  "$out/source_reconstruction_audit.json"

{
  echo "commit=$(git -C "$root" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "paper_artifact_commit=2b2d2fd4de69ee44a4363e69f8cfb82ceed132db"
  echo "paper_source_commit=c692d9581e17689ca1dc20545c48a355c6a86ff6"
  echo "paper_coverage_blob=5c5f0e9b4b4a5b548504653680d0cf158d2db613"
  echo "python=$(python3 --version 2>&1)"
} > "$out/environment.txt"

cat > "$out/README.txt" <<'EOF'
P9c reconciles Extended SP3 coverage with the final InterSpec paper's field-level
SP3 counts.

p9c-report.json records source integrity, source-reconstruction status,
capability-resolution status, and prototype mapping status.
p9c-cases.csv contains exactly 32 stable paper count-unit identifiers.
source_reconstruction_audit.json records the evidence supporting the
source-fidelity limitation.
P9C_RESULTS.md is mechanically rendered from the machine-readable artifacts.

The final paper denominator is reproduced exactly. The preserved paper artifact
does not retain a one-row-per-paper-field identity map, and the raw reports are
not consistently paper-aligned. P9c therefore completes in source-fidelity-
limitation mode and does not report a guessed Extended SP3 percentage over the
32 fields.
EOF

echo "P9c coverage results written to $out"
