#!/usr/bin/env python3
"""Recompute the archived hosted reference without treating it as paper data.

This script reads original raw samples. It never changes measurements, drops
unfavorable pairs, invents zeroes for missing cells, or aggregates different
hosts into a single publication number.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
FOUR = ("native", "rlbox-only", "tracked-no-check", "interspec")
FOUR_UNDERSCORED = ("native", "rlbox_only", "tracked_no_check", "extended_sp3")
SOURCES = {
    "memcached": {
        "path": "evaluation/results/completion/hosted-38092306794/matrix-raw.csv",
        "run": 38092306794,
        "groups": ("balanced_1c", "balanced_8c", "read_heavy_1k",
                   "write_heavy", "watch_light", "watch_moderate"),
        "repetitions": 5,
        "variants": FOUR,
        "group_key": "scenario",
        "mode_key": "variant",
        "measure": "ops_per_s",
        "kind": "throughput",
    },
    "nginx": {
        "path": "evaluation/results/nginx-pcre/hosted-37835791042/performance/samples.csv",
        "run": 37835791042,
        "groups": ("4", "8"),
        "repetitions": 5,
        "variants": FOUR,
        "group_key": "threads",
        "mode_key": "variant",
        "measure": "requests_per_s",
        "kind": "throughput",
    },
    "yaml": {
        "path": "evaluation/results/yaml-libyaml/hosted-37593628736/yaml-performance.csv",
        "run": 37593628736,
        "groups": ("yaml_parse_1mb",),
        "repetitions": 15,
        "variants": FOUR_UNDERSCORED,
        "group_key": "workload",
        "mode_key": "mode",
        "measure": "total_ns",
        "kind": "duration",
    },
    "rsync": {
        "path": "evaluation/results/rsync-popt/rsync-performance.csv",
        "run": None,
        "groups": ("option_parse", "local_dry_run", "file_sync_194mb"),
        "repetitions": 15,
        "variants": FOUR_UNDERSCORED,
        "group_key": "workload",
        "mode_key": "mode",
        "measure": "total_ns",
        "kind": "duration",
    },
}


class AuditError(RuntimeError):
    pass


def require(test: bool, message: str) -> None:
    if not test:
        raise AuditError(message)


def load_records(rel: str):
    path = ROOT / rel
    payload = path.read_bytes()
    rows = list(csv.DictReader(payload.decode("utf-8-sig").splitlines()))
    require(bool(rows), f"empty source {rel}")
    require(all(None not in record for record in rows), f"bad CSV columns {rel}")
    return rows, hashlib.sha256(payload).hexdigest()


def validate_measure(row: dict, name: str, source: str) -> float:
    try:
        value = float(row[name])
    except (ValueError, TypeError, KeyError) as error:
        raise AuditError(f"{source}: malformed {name}") from error
    require(0 < value < float("inf"), f"{source}: nonpositive or infinite {name}")
    return value


def audit_source(name: str, spec: dict):
    rows, digest = load_records(spec["path"])
    expected_groups = set(spec["groups"])
    expected_variants = set(spec["variants"])
    samples = {}
    for row in rows:
        group = row[spec["group_key"]]
        rep = int(row["repetition"])
        mode = row[spec["mode_key"]]
        key = (group, rep, mode)
        require(group in expected_groups, f"{name}: unexpected workload {group}")
        require(mode in expected_variants, f"{name}: unexpected mode {mode}")
        require(0 <= rep < spec["repetitions"], f"{name}: bad repetition {rep}")
        require(key not in samples, f"{name}: duplicate {key}")
        validate_measure(row, spec["measure"], name)
        if name == "memcached":
            require(row["errors"] == "0", f"{key}: application errors")
            require(row["valid_no_log_loss"] == "True", f"{key}: log loss")
            require(row["valid_no_lru_loss"] == "True", f"{key}: LRU loss")
            count = validate_measure(row, "operations", name)
            elapsed = validate_measure(row, "elapsed_s", name)
            actual = validate_measure(row, "ops_per_s", name)
            require(abs(count / elapsed - actual) <= 0.02,
                    f"{key}: inconsistent throughput")
        if name == "nginx":
            require(row["bad"] == "0", f"{key}: invalid responses")
            require(int(row["requests"]) == int(row["validated"]),
                    f"{key}: unvalidated responses")
            for field in ("connect_errors", "read_errors", "write_errors",
                          "status_errors", "timeouts"):
                require(row[field] == "0", f"{key}: {field}")
        samples[key] = row

    required = {
        (group, rep, mode)
        for group in spec["groups"]
        for rep in range(spec["repetitions"])
        for mode in spec["variants"]
    }
    require(set(samples) == required,
            f"{name}: missing {len(required - set(samples))} or extra samples")
    summaries = []
    for group in spec["groups"]:
        modes = {}
        for mode in spec["variants"]:
            values = [
                float(samples[(group, rep, mode)][spec["measure"]])
                for rep in range(spec["repetitions"])
            ]
            scale = 1000 if spec["kind"] == "throughput" else 1_000_000
            modes[mode] = round(median(values) / scale, 6)
        losses = []
        for rep in range(spec["repetitions"]):
            if spec["kind"] == "throughput":
                rlbox = float(samples[(group, rep, "rlbox-only")][spec["measure"]])
                protected = float(samples[(group, rep, "interspec")][spec["measure"]])
                losses.append(100 * (rlbox - protected) / rlbox)
            else:
                rlbox = float(samples[(group, rep, "rlbox_only")][spec["measure"]])
                protected = float(samples[(group, rep, "extended_sp3")][spec["measure"]])
                losses.append(100 * (protected / rlbox - 1))
        summaries.append({
            "workload": group,
            "median_by_variant": modes,
            "median_paired_overhead_pct": round(median(losses), 6),
            "paired_repetitions": spec["repetitions"],
        })
    return {
        "source": spec["path"],
        "sha256": digest,
        "workflow_run_id": spec["run"],
        "raw_samples": len(rows),
        "workload_count": len(spec["groups"]),
        "variants": list(spec["variants"]),
        "repetitions": spec["repetitions"],
        "unit": "Kops/s" if name == "memcached" else
                "Kreq/s" if name == "nginx" else "ms",
        "overhead_definition": ("paired throughput loss" if
                                spec["kind"] == "throughput" else
                                "paired runtime increase"),
        "results": summaries,
    }


def verify_archives():
    ledger = json.loads(
        (ROOT / "evaluation/results/selected/readiness.json").read_text()
    )
    checked = []
    for artifact in ledger["artifacts"]:
        path = ROOT / artifact["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        require(actual == artifact["sha256"],
                f"archived artifact mismatch: {artifact['path']}")
        checked.append({
            "source": artifact["path"],
            "sha256": actual,
            "workflow_run_id": artifact["workflow_run_id"],
        })
    return checked


def run():
    reports = {name: audit_source(name, spec)
               for name, spec in SOURCES.items()}
    return {
        "schema": 1,
        "scope": "archived_hosted_reference_only",
        "verified": True,
        "publication_ready": False,
        "applications": reports,
        "raw_samples_total": sum(x["raw_samples"] for x in reports.values()),
        "verified_archives": verify_archives(),
        "excluded_from_publication_claims": [
            "No controlled dedicated host measurements for the specified protocol",
            "Application studies were collected in distinct hosted runs",
            "No original-source zip/libzip integration data in this repository",
            "The new typed-pool runtime extension was not used in these archived runs",
            "YAML workload driver is project authored",
            "Original SP1/SP2 policy coverage and original paper PoCs remain unverified",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = run()
    content = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(content)
    print(json.dumps({
        "verified": True,
        "publication_ready": False,
        "samples": result["raw_samples_total"],
        "archives": len(result["verified_archives"]),
        "workloads": sum(x["workload_count"] for x in result["applications"].values()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
