#!/usr/bin/env python3
"""Independently audit native-versus-isolated correctness summary evidence.

This gate validates the observable workloads in application drivers; it is
not a proof of semantic equivalence for untested input or concurrency.
"""
import argparse
import hashlib
import json
from pathlib import Path

MODES = ("native", "rlbox-only", "tracked-no-check", "interspec")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def cases(data, key):
    rows = data.get("cases")
    require(isinstance(rows, list) and bool(rows), "missing cases")
    indexed = {}
    for row in rows:
        name = row.get(key)
        require(name and name not in indexed, "missing or duplicate case name")
        indexed[name] = row
    return indexed


def audit_rsync(data):
    rows = cases(data, "name")
    names = ("archive_transfer", "size_filter", "dry_run",
             "update_delete_backup", "invalid_numeric_option", "unknown_option")
    for name in names:
        row = rows.get(name)
        require(row is not None and row.get("pass") is True, "failed rsync case " + name)
        results = row.get("returncodes", {})
        require(set(results) == {"native", "integrated"} and
                results["native"] == results["integrated"], "rsync status mismatch " + name)
    for name in names[:3]:
        require(rows[name].get("manifests_equal") is True, "rsync manifest mismatch " + name)
    return {"paired_workloads": len(names), "matched_file_manifest_workloads": 3}


def audit_yaml(data):
    require(data.get("passed") is True, "YAML correctness gate failed")
    variants = data.get("variants", {})
    modes = ("native", "rlbox_only", "tracked_no_check", "extended_sp3")
    require(set(variants) == set(modes), "YAML missing variants")
    fields = ("iterations", "input_bytes", "events", "scalars", "scalar_bytes", "hash")
    signatures = [tuple(variants[name].get(key) for key in fields) for name in modes]
    require(all(x is not None for x in signatures[0]) and
            all(row == signatures[0] for row in signatures[1:]),
            "YAML semantic output mismatch")
    require(int(variants["extended_sp3"].get("checks", 0)) > 0, "YAML did not check scalars")
    return {"matched_variants": 4, "events_per_variant": int(variants["native"]["events"]),
            "scalars_per_variant": int(variants["native"]["scalars"])}


def audit_nginx(data):
    require(data.get("passed") is True, "nginx correctness failed")
    rows = cases(data, "name")
    fields = ("http_cases", "keepalive_requests", "concurrent_requests",
              "reloads", "concurrent_requests_after_reload")
    expected = []
    for mode in MODES:
        name = "normal/" + mode
        require(rows.get(name, {}).get("passed") is True, "nginx normal failed " + mode)
        detail = rows[name].get("detail", {})
        expected.append(tuple(detail.get(key) for key in fields))
        require(rows.get("invalid-config/" + mode, {}).get("passed") is True,
                "nginx invalid config failed " + mode)
    require(all(value is not None for value in expected[0]) and
            all(value == expected[0] for value in expected[1:]),
            "nginx observation counts differ")
    for mode in ("native", "interspec"):
        detail = rows.get("workers-reload/" + mode, {})
        require(detail.get("passed") is True and
                detail.get("detail", {}).get("reloads", 0) >= 2,
                "nginx worker reload failed " + mode)
    return {"matched_variants": 4, "reload_modes": 2, "error_path_modes": 4}


def audit_memcached(data):
    rows = cases(data, "case")
    require(data.get("passed") == data.get("total") == len(rows),
            "memcached incomplete correctness matrix")
    baseline = None
    for mode in (*MODES, "diagnostics"):
        row = rows.get("normal-" + mode)
        require(row and row.get("pass") is True, "memcached normal failed " + mode)
        checks = row.get("checks")
        require(isinstance(checks, list) and len(set(checks)) == len(checks) >= 16 and
                row.get("checks_passed") == len(checks), "memcached missing assertions")
        if baseline is None:
            baseline = set(checks)
        require(set(checks) == baseline, "memcached cases differ " + mode)
    for mode in ("native", "interspec"):
        require(rows.get("upstream-" + mode, {}).get("pass") is True,
                "memcached upstream tests failed " + mode)
    return {"matched_variants": 5, "contract_assertions_per_variant": len(baseline),
            "upstream_test_modes": 2}


AUDITORS = {"rsync": audit_rsync, "yaml": audit_yaml,
            "nginx": audit_nginx, "memcached": audit_memcached}


def audit(paths):
    payload = {name: json.loads(path.read_text()) for name, path in paths.items()}
    return {"status": "passed", "scope": "tested_behavioral_observables",
            "audits": {name: AUDITORS[name](data) for name, data in payload.items()},
            "evidence_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                                for name, path in paths.items()}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--app", choices=sorted(AUDITORS))
    p.add_argument("--evidence", type=Path)
    p.add_argument("--out", type=Path)
    for name in AUDITORS:
        p.add_argument("--" + name, type=Path)
    args = p.parse_args()
    paths = {name: getattr(args, name) for name in AUDITORS}
    if args.app and args.evidence:
        paths = {args.app: args.evidence}
    elif args.app or args.evidence or any(path is None for path in paths.values()):
        p.error("provide --app and --evidence, or all four named files")
    report = audit(paths)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

