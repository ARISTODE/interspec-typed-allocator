#!/usr/bin/env python3
"""Benign run of a registry port against its native build (items I7 to I12).

For every case in the boundary's corpus and for one and two iterations (or the
iteration counts the case lists), the
native program and the three isolated variants (RLBox-only, tracking without
check, InterSpec with all three policies on) run once each. Every isolated run
must exit 0, print one result line whose result fields equal the native run's,
report the expected number of registry checks, and write nothing to stderr but
the wrapper's configuration line. Raw output is written before anything is
compared; nothing is retried. Elapsed time in the output is not used.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

VARIANTS = ("native", "rlbox-only", "tracked-no-check", "interspec")

# Per boundary: binary prefix, result-line tag, how a case becomes arguments,
# and the fields that are not part of the result.
BOUNDARIES = {
    "ucl_libucl": {
        "prefix": "ucl", "tag": "UCL_BENCH",
        "args": lambda corpus, case, n: [str(corpus / case["document"]), case["key1"],
                                         case["key2"], n],
        "name": lambda case: f"{Path(case['document']).stem}__{case['key1']}__{case['key2']}",
    },
    "zip_libzip": {
        "prefix": "zip", "tag": "ZIP_BENCH",
        "args": lambda corpus, case, n: [str(corpus / case["archive"]), n],
        "name": lambda case: Path(case["archive"]).stem,
    },
    "magick_libpng": {
        "prefix": "png", "tag": "PNG_BENCH",
        "args": lambda corpus, case, n: [str(corpus / case["image"]), n],
        "name": lambda case: Path(case["image"]).stem,
    },
    "ffmpeg_libvpx": {
        "prefix": "vpx", "tag": "VPX_BENCH",
        "args": lambda corpus, case, n: [case["width"], case["height"], n],
        "name": lambda case: f"{case['width']}x{case['height']}",
    },
    # U allocates no registered object at this boundary. The registry holds
    # T's objects; one check per round on what SSL_get_ex_data returns. The
    # tracking-without-check variant registers T's objects and never checks.
    "nginx_openssl": {
        "prefix": "tls", "tag": "TLS_BENCH",
        "variants": ("native", "rlbox-only", "tracked-no-check", "interspec"),
        "args": lambda corpus, case, n: [case["request_bytes"], case["response_bytes"], n],
        "name": lambda case: f"{case['request_bytes']}_{case['response_bytes']}",
    },
    # No registry at this boundary (U returns a number): no variant performs
    # a registry check.
    "memcached_hash": {
        "prefix": "hash", "tag": "HASH_BENCH",
        "variants": ("native", "rlbox-only", "interspec"), "registry": False,
        "args": lambda corpus, case, n: [case["keyspace"], n],
        "name": lambda case: f"keyspace{case['keyspace']}",
    },
    # The hash table in U: the registry holds T's items; one check for every
    # item that U hands back. No object of U is registered; the
    # tracking-without-check variant registers T's items, uses the registry's
    # tokens as handles and never checks a handle against the registry.
    "memcached_assoc": {
        "prefix": "assoc", "tag": "ASSOC_BENCH", "reported_as": "memcached_hash",
        "variants": ("native", "rlbox-only", "tracked-no-check", "interspec"),
        "args": lambda corpus, case, n: [case["keyspace"], n],
        "name": lambda case: f"keyspace{case['keyspace']}",
    },
}
NOT_RESULT = {"variant", "checks", "elapsed_ns"}


def parse(tag, stdout):
    lines = stdout.splitlines()
    if len(lines) != 1 or not lines[0].startswith(tag + " "):
        return None
    fields = dict(token.split("=", 1) for token in lines[0].split()[1:])
    return fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary", required=True, choices=sorted(BOUNDARIES))
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--bin", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    spec = BOUNDARIES[args.boundary]
    cases = json.loads((args.corpus / "cases.json").read_text())["cases"]
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "INTERSPEC_SP1": "1",
           "INTERSPEC_SP2": "1", "INTERSPEC_SP3": "1", "INTERSPEC_POLICY_REPORT": "1"}
    args.out.mkdir(parents=True)

    variants = spec.get("variants", VARIANTS)
    plan = []
    for case in cases:
        for iterations in case.get("iterations", ("1", "2")):
            for variant in variants:
                run = f"{spec['name'](case).replace('/', '_')}__x{iterations}__{variant}"
                binary = args.bin / f"{spec['prefix']}-{variant}"
                plan.append((run, case, iterations, variant,
                             [str(binary)] + spec["args"](args.corpus, case, iterations)))
    for run, _, _, _, command in plan:
        directory = args.out / run
        directory.mkdir()
        done = subprocess.run(command, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=300)
        (directory / "command.json").write_text(json.dumps(command) + "\n")
        (directory / "stdout.txt").write_bytes(done.stdout)
        (directory / "stderr.txt").write_bytes(done.stderr)
        (directory / "exit_code.txt").write_text(f"{done.returncode}\n")

    def load(run):
        directory = args.out / run
        return (int((directory / "exit_code.txt").read_text()),
                (directory / "stdout.txt").read_text(errors="replace"),
                (directory / "stderr.txt").read_text(errors="replace"))

    rows, failures = [], 0
    native = {}
    for run, case, iterations, variant, _ in plan:
        code, stdout, stderr = load(run)
        fields = parse(spec["tag"], stdout)
        key = (spec["name"](case), iterations)
        checks = {"exit_zero": code == 0, "one_result_line": fields is not None}
        if variant == "native":
            native[key] = fields
            checks["no_stderr"] = stderr == ""
        elif fields is not None and native.get(key) is not None:
            checks["variant"] = fields.get("variant") == variant
            checks["result_matches_native"] = (
                {k: v for k, v in fields.items() if k not in NOT_RESULT}
                == {k: v for k, v in native[key].items() if k not in NOT_RESULT})
            count = int(fields.get("checks", "-1"))
            checks["checks"] = (count > 0 if variant == "interspec" and
                                spec.get("registry", True) else count == 0)
            other = [l for l in stderr.splitlines() if not l.startswith("INTERSPEC_POLICY ")]
            checks["no_other_stderr"] = not other
            if variant == "interspec":
                checks["reports_all_on"] = (
                    f"INTERSPEC_POLICY boundary={spec.get('reported_as', args.boundary)} "
                    "sp1=1 sp2=1 sp3=full" in stderr)
        else:
            checks["native_reference_available"] = False
        passed = all(checks.values())
        failures += not passed
        rows.append({"run": run, "passed": passed, "checks": checks})
        if not passed:
            print(f"FAIL {run}: " + ", ".join(k for k, v in checks.items() if not v))
    summary = {"boundary": args.boundary, "total": len(rows), "passed": len(rows) - failures,
               "binaries_sha256": {v: hashlib.sha256(
                   (args.bin / f"{spec['prefix']}-{v}").read_bytes()).hexdigest()
                   for v in variants},
               "runs": rows}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"{args.boundary} benign: {summary['passed']}/{summary['total']} runs passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
