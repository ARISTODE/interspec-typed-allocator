#!/usr/bin/env python3

import importlib.util
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "build_p9c_report.py"

spec = importlib.util.spec_from_file_location("build_p9c_report", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

report = module.build(
    ROOT,
    ROOT / "evaluation" / "p9c" / "interspec_paper_integrity_coverage.csv",
    ROOT / "evaluation" / "p9c" / "paper_sp3_manifest.json",
)

assert report["paper_source_integrity"]
assert report["classification_explicit"]
assert report["paper"]["sp3_case_count"] == 32
assert report["paper"]["expected_sp3_case_count"] == 32
assert report["paper"]["boundary_count"] == 10
assert report["classification"]["eligible"] == 0
assert report["classification"]["ineligible"] == 0
assert report["classification"]["insufficient_source_metadata"] == 32
assert not report["capability_resolution_complete"]
assert not report["source_fidelity_complete"]
assert report["prototype"]["demonstrated_exact_paper_cases"] == 0

expected = {
    "ffmpeg/libvpx": 2,
    "magick/libpng": 3,
    "memcached/bipbuffer": 2,
    "memcached/hash": 4,
    "nginx/libpcre": 2,
    "nginx/openssl": 5,
    "rsync/popt": 7,
    "ucl/libucl": 3,
    "yaml/libyaml": 1,
    "zip/libzip": 3,
}
actual = {row["boundary"]: row["sp3_fields"] for row in report["paper"]["boundaries"]}
assert actual == expected

ids = [case["paper_case_id"] for case in report["cases"]]
assert len(ids) == len(set(ids)) == 32

with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "cases.csv"
    module.write_cases(out, report["cases"])
    assert out.read_text(encoding="utf-8").count("\n") == 33

print("P9c paper coverage reconciliation tests passed")
