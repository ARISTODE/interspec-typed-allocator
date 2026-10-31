#!/usr/bin/env python3
"""Positive and deliberately corrupted controls for pointer-origin evidence."""
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from summarize_pointer_census import CASES, REQUIRED, summarize


def line(app, site, direction, origin):
    return (f"INTERSPEC_POINTER_CENSUS schema=1 pid=123 boundary={app} "
            f"direction={direction} site={site} storage={origin} "
            "address=0x1234 result=observed\n")


class PointerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="interspec-census-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def populate(self, app):
        for relative in CASES[app]:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("ordinary log\n")
        first = self.root / CASES[app][0]
        rows = []
        for site in REQUIRED[app]:
            if site.startswith("checked_"):
                direction, origin = "u_to_t", "u_tracked_heap"
            elif site in ("shadow_destination", "capture_offsets_output",
                          "lru_item_tokenized", "peek_all_size_output"):
                direction, origin = "t_adapter_only", "t_stack"
            else:
                direction, origin = "t_to_u", "t_image_static"
            rows.append(line(app, site, direction, origin))
        first.write_text("".join(rows))
        return first

    def test_all_boundaries(self):
        for app in CASES:
            with self.subTest(app=app):
                self.populate(app)
                result = summarize(app, self.root)
                self.assertEqual(result["total_observations"], len(REQUIRED[app]))
                self.assertEqual(len(result["cases"]), len(CASES[app]))

    def test_missing_log_rejected(self):
        self.populate("rsync_popt")
        (self.root / CASES["rsync_popt"][-1]).unlink()
        with self.assertRaises(FileNotFoundError):
            summarize("rsync_popt", self.root)

    def test_missing_site_rejected(self):
        path = self.populate("yaml_libyaml")
        path.write_text("ordinary log only\n")
        with self.assertRaisesRegex(ValueError, "missing mandatory sites"):
            summarize("yaml_libyaml", self.root)

    def test_wrong_domain_rejected(self):
        path = self.populate("yaml_libyaml")
        with path.open("a") as out:
            out.write(line("yaml_libyaml", "checked_scalar_result", "u_to_t", "t_stack"))
        with self.assertRaisesRegex(ValueError, "mislabeled"):
            summarize("yaml_libyaml", self.root)

    def test_unknown_preserved(self):
        path = self.populate("yaml_libyaml")
        with path.open("a") as out:
            out.write(line("yaml_libyaml", "document_copy_source", "t_to_u", "unknown"))
        self.assertEqual(summarize("yaml_libyaml", self.root)["by_storage"]["unknown"], 1)

    def test_wrong_boundary_rejected(self):
        path = self.populate("yaml_libyaml")
        with path.open("a") as out:
            out.write(line("nginx_pcre", "wrong_site", "t_to_u", "unknown"))
        with self.assertRaisesRegex(ValueError, "wrong boundary"):
            summarize("yaml_libyaml", self.root)


if __name__ == "__main__":
    unittest.main()

