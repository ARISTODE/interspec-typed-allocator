#!/usr/bin/env python3
"""Count original rsync app calls; separate isolated API from trusted host helper.

This counts native observation candidates, not actual sandbox pointer transport.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

PIN = "7c20b077c980036a19587701cec320cc88e42a4a"
PROGRAM_SOURCE = {"rsync": "options.c", "tls": "tls.c"}
ISOLATED_API_ROLES = {"u_to_t_bad_option_pointer", "t_to_u_context_pointer"}
HOST_HELPER_ROLE = "host_helper_error_pointer_not_isolated"


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
        data = (src / file).read_bytes()
        assert data == subprocess.check_output(
            ["git", "-C", str(src), "show", f"HEAD:{file}"]), file
        originals[file] = hashlib.sha256(data).hexdigest()
    parity = json.loads((args.output_dir / "native-parity.json").read_text())
    assert parity["parity"] == "pass"
    summary = {
        "schema": 2, "benchmark": "rsync/popt",
        "scope": "original native rsync and auxiliary tls invalid-option sites",
        "isolated_interface": "poptBadOption is routed via the deployed P4c bridge",
        "nonisolated_host_helper": "poptStrerror remains trusted-side in the deployed P4c bridge",
        "isolation": "not directly measured; native observations only",
        "source_revision": PIN, "source_sha256": originals,
        "native_parity": "pass", "programs": {},
    }
    totals = Counter()
    for program, file in PROGRAM_SOURCE.items():
        binary = args.binary_dir / program
        trace = args.output_dir / f"{program}-original-pointer-events.jsonl"
        assert hashlib.sha256(trace.read_bytes()).hexdigest() == parity["raw_trace_sha256"][program]
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == parity["binary_sha256"][f"traced/{program}"]
        events = [json.loads(s) for s in trace.read_text().splitlines() if s.strip()]
        assert events and all(r["schema"] == 2 and r["api"] in
                              ("poptBadOption", "poptStrerror") for r in events)
        pcs = sorted({int(r["caller_pc"], 16) for r in events})
        resolved = subprocess.check_output(
            ["addr2line", "-e", str(binary), "-f", "-C",
             *[f"0x{pc-1:x}" for pc in pcs]], text=True).splitlines()
        assert len(resolved) == 2 * len(pcs)
        locations = {}
        for i, pc in enumerate(pcs):
            function, fileline = resolved[2*i:2*i+2]
            filename, _, lineno = fileline.rpartition(":")
            try:
                relative = Path(filename).resolve().relative_to(src).as_posix()
                number = int(lineno.split(" ", 1)[0])
            except (ValueError, OSError):
                relative, number = fileline, 0
            locations[pc] = {
                "file": relative, "line": number, "function": function,
                "accepted": relative == file and number > 0,
            }
        accepted, excluded = Counter(), Counter()
        for record in events:
            location = locations[int(record["caller_pc"], 16)]
            key = (location["file"], location["line"],
                   record["api"], record["role"], record["origin"])
            (accepted if location["accepted"] else excluded)[key] += 1
        assert accepted and not excluded, (program, accepted, excluded)
        assert any(k[3] == "u_to_t_bad_option_pointer" for k in accepted), program
        assert any(k[3] == HOST_HELPER_ROLE for k in accepted), program
        by_role = Counter()
        for (path, line, api, role, origin), n in accepted.items():
            by_role[role + ":" + origin] += n
            totals[role + ":" + origin] += n
        summary["programs"][program] = {
            "total_records": len(events),
            "accepted_original_source_records": sum(accepted.values()),
            "excluded_non_app_records": sum(excluded.values()),
            "pointer_events_by_role_and_origin": dict(sorted(by_role.items())),
            "isolated_api_candidate_return_events": sum(
                n for k, n in accepted.items()
                if k[3] == "u_to_t_bad_option_pointer"),
            "trusted_host_helper_return_events_excluded": sum(
                n for k, n in accepted.items() if k[3] == HOST_HELPER_ROLE),
            "original_callsite_events": [
                {"file": k[0], "line": k[1], "api": k[2],
                 "role": k[3], "origin": k[4], "events": n}
                for k, n in sorted(accepted.items())
            ],
            "raw_trace_sha256": parity["raw_trace_sha256"][program],
        }
    summary["all_programs_role_and_origin"] = dict(sorted(totals.items()))
    summary["main_rsync_isolated_api_candidate_return_events"] = \
        summary["programs"]["rsync"]["isolated_api_candidate_return_events"]
    summary["main_rsync_host_helper_returns_excluded"] = \
        summary["programs"]["rsync"]["trusted_host_helper_return_events_excluded"]
    (args.output_dir / "source-only-runtime-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(json.dumps({
        "native_parity": "pass",
        "main_rsync_bad_option_candidate_returns":
            summary["main_rsync_isolated_api_candidate_return_events"],
        "main_rsync_host_helper_excluded":
            summary["main_rsync_host_helper_returns_excluded"],
        "all_roles_by_origin": summary["all_programs_role_and_origin"],
    }))


if __name__ == "__main__":
    main()
