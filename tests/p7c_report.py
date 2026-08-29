#!/usr/bin/env python3

import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.p7c_report import build_report


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def test_repository_manifest_is_incremental():
    manifest = json.loads((ROOT / "integration/p7c_manifest.json").read_text())
    report = build_report(ROOT, manifest)
    assert not report["complete"]
    assert report["completed_new_boundaries"] == 0
    assert report["missing_pointer_shapes"] == [
        "buffer_with_extent",
        "interior_u_object",
        "structured_u_output",
    ]

    baseline = next(b for b in report["boundaries"] if b["name"] == "rsync/popt")
    assert baseline["complete"]
    assert baseline["inferred_allocation_sites"] == 2
    assert baseline["precise_source_allocation_sites"] == 2
    assert baseline["helper_sites"] == 1
    assert baseline["trusted_uses"] == 1


def test_complete_report_requires_count_and_shape_coverage():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        policy = {
            "types": ["A"],
            "allocations": [
                {
                    "function": "make_a",
                    "type": "A",
                    "site": {
                        "start_line": 1,
                        "start_column": 1,
                        "end_line": 1,
                        "end_column": 8,
                    },
                }
            ],
            "uses": [{"name": "use_a", "type": "A", "offset": 0, "bytes": 4}],
        }
        write_json(root / "policy.json", policy)
        write_json(root / "boundary.json", {"helper_sites": []})

        shapes = ["interior_u_object", "structured_u_output", "buffer_with_extent"]
        boundaries = []
        for index, shape in enumerate(shapes):
            boundaries.append({
                "name": f"boundary-{index}",
                "role": "p7c",
                "status": "full",
                "pointer_shapes": [shape],
                "policy": "policy.json",
                "boundary_policy": "boundary.json",
                "source_revision": f"rev-{index}",
                "adversarial": ["wrong_type_or_wrong_object", "untracked"],
            })

        manifest = {
            "schema_version": 1,
            "required_new_boundaries": 3,
            "required_pointer_shapes": shapes,
            "boundaries": boundaries,
        }
        report = build_report(root, manifest)
        assert report["complete"]
        assert report["completed_new_boundaries"] == 3
        assert report["missing_pointer_shapes"] == []
        assert all(b["precise_source_fraction"] == 1.0 for b in report["boundaries"])

        manifest["boundaries"][2]["status"] = "planned"
        report = build_report(root, manifest)
        assert not report["complete"]
        assert report["completed_new_boundaries"] == 2
        assert report["missing_pointer_shapes"] == ["buffer_with_extent"]


if __name__ == "__main__":
    test_repository_manifest_is_incremental()
    test_complete_report_requires_count_and_shape_coverage()
    print("P7c report tests: ok")
