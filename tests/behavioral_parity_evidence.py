#!/usr/bin/env python3
"""Controls that require matched historical application evidence to be intact."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_behavioral_parity import audit, audit_rsync, audit_yaml, audit_nginx, audit_memcached

PATHS = {
    "rsync": ROOT / "evaluation/results/sp3-diagnostics/summary.json",
    "yaml": ROOT / "evaluation/results/yaml-libyaml/hosted-37593628736/correctness.json",
    "nginx": ROOT / "evaluation/results/nginx-pcre/hosted-37835791042/correctness/summary.json",
    "memcached": ROOT / "evaluation/results/completion/hosted-38092306794/correctness.json",
}


class ParityEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = {name: json.loads(path.read_text()) for name, path in PATHS.items()}

    def test_all_applications(self):
        self.assertEqual(set(audit(PATHS)["audits"]), set(PATHS))

    def test_rsync_bad_manifest(self):
        data = copy.deepcopy(self.data["rsync"])
        next(x for x in data["cases"] if x["name"] == "size_filter")["manifests_equal"] = False
        with self.assertRaises(ValueError):
            audit_rsync(data)

    def test_rsync_missing_native_comparison(self):
        data = copy.deepcopy(self.data["rsync"])
        next(x for x in data["cases"] if x["name"] == "dry_run")["returncodes"].pop("native")
        with self.assertRaises(ValueError):
            audit_rsync(data)

    def test_yaml_hash_mismatch(self):
        data = copy.deepcopy(self.data["yaml"])
        data["variants"]["extended_sp3"]["hash"] = "changed"
        with self.assertRaises(ValueError):
            audit_yaml(data)

    def test_yaml_check_missing(self):
        data = copy.deepcopy(self.data["yaml"])
        data["variants"]["extended_sp3"]["checks"] = 0
        with self.assertRaises(ValueError):
            audit_yaml(data)

    def test_nginx_reload_missing(self):
        data = copy.deepcopy(self.data["nginx"])
        next(x for x in data["cases"] if x["name"] == "workers-reload/interspec")["detail"]["reloads"] = 0
        with self.assertRaises(ValueError):
            audit_nginx(data)

    def test_nginx_variant_mismatch(self):
        data = copy.deepcopy(self.data["nginx"])
        next(x for x in data["cases"] if x["name"] == "normal/interspec")["detail"]["http_cases"] = 99
        with self.assertRaises(ValueError):
            audit_nginx(data)

    def test_memcached_missing_assertion(self):
        data = copy.deepcopy(self.data["memcached"])
        next(x for x in data["cases"] if x["case"] == "normal-interspec")["checks"].pop()
        with self.assertRaises(ValueError):
            audit_memcached(data)

    def test_memcached_missing_upstream(self):
        data = copy.deepcopy(self.data["memcached"])
        data["cases"] = [x for x in data["cases"] if x["case"] != "upstream-interspec"]
        data["passed"] -= 1
        data["total"] -= 1
        with self.assertRaises(ValueError):
            audit_memcached(data)


if __name__ == "__main__":
    unittest.main()

