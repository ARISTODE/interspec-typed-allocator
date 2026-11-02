#!/usr/bin/env python3
"""Resolve and count ONLY original memcached application pointer callsites.

No wrapper, test harness, generated bridge, or diagnostic callsite is included.
This is a native execution observation, not an isolated-boundary coverage claim.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

MEMCACHED_PIN = "2d51e364799bc9698bd4b11728ea978cea12da6e"
ALLOWED = {"logger.c", "items.c"}
INPUT_ROLES = {"t_to_u_data", "t_to_u_outparam"}


def output(command):
    return subprocess.check_output(command, text=True).strip()


def check_upstream(source):
    revision = output(["git", "-C", str(source), "rev-parse", "HEAD"])
    assert revision == MEMCACHED_PIN, f"unexpected original revision: {revision}"
    result = {}
    for name in ("logger.c", "items.c", "bipbuffer.c", "bipbuffer.h"):
        original = subprocess.check_output(["git", "-C", str(source), "show", f"HEAD:{name}"])
        current = (source / name).read_bytes()
        assert original == current, f"upstream original code changed: {name}"
        result[name] = hashlib.sha256(current).hexdigest()
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--events", type=Path, required=True)
    p.add_argument("--parity", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    source = args.source.resolve()
    original_sha = check_upstream(source)
    parity = json.loads(args.parity.read_text())
    assert parity["parity"] == "pass"
    assert hashlib.sha256(args.events.read_bytes()).hexdigest() == parity["sha256"]["raw_trace"]
    assert hashlib.sha256(args.binary.read_bytes()).hexdigest() == parity["sha256"]["traced_binary"]
    raw = [json.loads(line) for line in args.events.read_text().splitlines() if line.strip()]
    assert raw, "native original source runtime trace is empty"
    assert all(r["schema"] == 1 for r in raw)
    pcs = sorted({int(r["caller_pc"], 16) for r in raw})
    assert all(pc > 0 for pc in pcs)
    decoded = output(["addr2line", "-e", str(args.binary), "-f", "-C",
                      *[f"0x{pc-1:x}" for pc in pcs]]).splitlines()
    assert len(decoded) == 2 * len(pcs), (len(decoded), len(pcs))
    locations = {}
    for i, pc in enumerate(pcs):
        function, fileline = decoded[2*i], decoded[2*i+1]
        path_text, _, line_text = fileline.rpartition(":")
        path = Path(path_text)
        try:
            relative = path.resolve().relative_to(source).as_posix()
            original = relative in ALLOWED
            line = int(line_text.split(" ", 1)[0])
        except (ValueError, OSError):
            relative, original, line = fileline, False, 0
        locations[pc] = {"function": function, "file": relative,
                         "line": line, "upstream_original": original}
    accepted, excluded = [], []
    for event in raw:
        caller = locations[int(event["caller_pc"], 16)]
        annotated = {**event, "callsite": caller}
        (accepted if caller["upstream_original"] else excluded).append(annotated)
    assert accepted, "no original upstream logger.c/items.c callsites resolved"
    assert not excluded, f"unexpected non-original callers: {excluded[:3]}"
    input_events = [r for r in accepted if r["role"] in INPUT_ROLES]
    stack_events = [r for r in input_events if r["origin"] == "t_stack"]
    image_events = [r for r in input_events
                    if r["origin"] == "t_image_readonly_candidate"]
    heap_returns = [r for r in accepted if r["origin"] == "u_heap_interior"]
    assert stack_events, "stack pointer arguments not exercised"
    assert image_events, "static image pointer arguments not exercised"
    assert heap_returns, "heap-interior result pointers not exercised"
    # This is an upstream literal callsite, not a wrapper-supplied test literal.
    assert any(r["api"] == "bipbuf_offer" and
               r["callsite"]["file"] == "logger.c" and
               abs(r["callsite"]["line"] - 1141) <= 3
               for r in image_events), "original logger.c static string callsite not hit"
    sites = Counter((r["callsite"]["file"], r["callsite"]["line"],
                     r["api"], r["role"], r["origin"]) for r in accepted)
    summary = {
        "schema": 1,
        "benchmark": "memcached/bipbuffer",
        "scope": "native-unchanged-upstream-original-callsite-events",
        "coverage": "selected direct bipbuffer pointer arguments and returns; not exhaustive",
        "isolation": "not measured; native workload only",
        "source_revision": MEMCACHED_PIN,
        "original_source_sha256": original_sha,
        "raw_trace_sha256": parity["sha256"]["raw_trace"],
        "parity": "pass",
        "total_raw_pointer_events": len(raw),
        "accepted_original_pointer_events": len(accepted),
        "excluded_non_original_events": len(excluded),
        "accepted_unique_observed_source_expressions": len(sites),
        "pointer_events_by_origin": dict(sorted(Counter(r["origin"] for r in accepted).items())),
        "application_input_pointer_events_by_origin": dict(sorted(
            Counter(r["origin"] for r in input_events).items())),
        "pointer_events_by_api_role": dict(sorted(
            Counter(f'{r["api"]}:{r["role"]}' for r in accepted).items())),
        "upstream_source_sites": [
            {"file": k[0], "line": k[1], "api": k[2], "role": k[3],
             "origin": k[4], "pointer_events": v}
            for k, v in sorted(sites.items())
        ],
    }
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({
        "native_parity": summary["parity"],
        "original_pointer_events": summary["accepted_original_pointer_events"],
        "stack_input_events": len(stack_events),
        "image_input_events": len(image_events),
        "heap_interior_return_events": len(heap_returns),
        "distinct_observed_sites": len(sites),
        "raw_trace_sha256": summary["raw_trace_sha256"],
    }))


if __name__ == "__main__":
    main()
