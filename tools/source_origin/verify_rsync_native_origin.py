#!/usr/bin/env python3
"""Attribute native popt error-string returns only to original rsync callers."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

PIN = "7c20b077c980036a19587701cec320cc88e42a4a"
PROGRAM_SOURCE = {"rsync": "options.c", "tls": "tls.c"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--binary-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    src = args.source.resolve()
    assert subprocess.check_output(["git", "-C", str(src), "rev-parse", "HEAD"],
                                   text=True).strip() == PIN
    originals = {}
    for file in ("options.c", "tls.c", "popt/popt.c", "popt/popt.h"):
        expected = subprocess.check_output(["git", "-C", str(src), "show", f"HEAD:{file}"])
        data = (src / file).read_bytes()
        assert data == expected, f"original source modified: {file}"
        originals[file] = hashlib.sha256(data).hexdigest()
    parity = json.loads((args.output_dir / "native-parity.json").read_text())
    assert parity["parity"] == "pass"
    summary = {"schema": 1, "benchmark": "rsync/popt",
               "scope": "native-original-application-poptStrerror-returns",
               "coverage": "selected native invalid-option paths, not exhaustive",
               "isolation": "not measured",
               "upstream_revision": PIN, "original_source_sha256": originals,
               "parity": "pass", "programs": {}}
    counts = Counter()
    for program, file in PROGRAM_SOURCE.items():
        binary = args.binary_dir / program
        trace = args.output_dir / f"{program}-original-pointer-events.jsonl"
        assert hashlib.sha256(trace.read_bytes()).hexdigest() == parity["raw_trace_sha256"][program]
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == parity["binary_sha256"][f"traced/{program}"]
        rows = [json.loads(s) for s in trace.read_text().splitlines() if s.strip()]
        assert rows and all(r["schema"] == 1 and r["api"] == "poptStrerror" for r in rows)
        pcs = sorted({int(r["caller_pc"], 16) for r in rows})
        output = subprocess.check_output(
            ["addr2line", "-e", str(binary), "-f", "-C",
             *[f"0x{pc-1:x}" for pc in pcs]], text=True).splitlines()
        assert len(output) == len(pcs)*2
        sites = {}
        for i, pc in enumerate(pcs):
            fn, fileline = output[2*i:2*i+2]
            filename, _, lineno = fileline.rpartition(":")
            try:
                rel = Path(filename).resolve().relative_to(src).as_posix()
                line = int(lineno.split(" ", 1)[0])
            except (ValueError, OSError):
                rel, line = fileline, 0
            sites[pc] = {"file": rel, "line": line, "function": fn,
                         "accepted": rel == file and line > 0}
        site_counts = Counter()
        excluded = Counter()
        for row in rows:
            site = sites[int(row["caller_pc"], 16)]
            key = (site["file"], site["line"], row["origin"])
            if site["accepted"]:
                site_counts[key] += 1
                counts[row["origin"]] += 1
            else:
                excluded[key] += 1
        assert site_counts, f"no original {file} poptStrerror calls observed"
        summary["programs"][program] = {
            "original_source_caller": file,
            "total_records": len(rows),
            "accepted_original_source_events": sum(site_counts.values()),
            "excluded_non_application_events": sum(excluded.values()),
            "origin_counts": dict(sorted(Counter({
                origin: sum(n for (f, l, o), n in site_counts.items() if o == origin)
                for (_, _, origin) in site_counts
            }).items())),
            "original_sites": [
                {"file": k[0], "line": k[1], "origin": k[2], "events": n}
                for k, n in sorted(site_counts.items())
            ],
            "excluded_sites": [
                {"file": k[0], "line": k[1], "origin": k[2], "events": n}
                for k, n in sorted(excluded.items())
            ],
            "raw_trace_sha256": parity["raw_trace_sha256"][program],
        }
    summary["all_accepted_original_events_by_origin"] = dict(sorted(counts.items()))
    summary["total_accepted_original_events"] = sum(counts.values())
    (args.output_dir / "source-only-runtime-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"parity": summary["parity"],
                      "source_only_events": summary["total_accepted_original_events"],
                      "origin_counts": summary["all_accepted_original_events_by_origin"],
                      "program_sites": {k: v["original_sites"] for k, v in summary["programs"].items()}}))


if __name__ == "__main__":
    main()
