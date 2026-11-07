#!/usr/bin/env python3
"""Fail early if an H1 legitimate fault-only binary cannot serve normally.

Save the actual stdout/stderr/protocol evidence even when the smoke fails.
This prevents a long 50-case-per-fault run from relying on invalid controls.
"""
import argparse
from pathlib import Path
import sys

from run_sp3_security_delta import run_memcached


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("/tmp/interspec-memcached-deployment"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    valid = True
    for variant in ("h1-rlbox", "h1-extended"):
        case = f"legitimate-{variant}"
        record = run_memcached(args.work, args.out, case, variant,
                               role=1, target=2, mode=0, census=False)
        directory = args.out / "cases" / case
        import json
        protocol = json.loads((directory / "protocol.json").read_text())
        stderr = (directory / "server.stderr").read_text(errors="replace") if (
            directory / "server.stderr").exists() else ""
        healthy = (record["status"] == "observed" and
                   record.get("alive_before_teardown") is True and
                   protocol.get("version") is True and
                   protocol.get("watch_event_types") == ["deleted", "item_get", "item_store"] and
                   "INTERSPEC_REJECT" not in stderr and
                   "AddressSanitizer" not in stderr and "runtime error:" not in stderr)
        print(f"SP3 H1 legitimate smoke {variant}: {'pass' if healthy else 'FAIL'}", flush=True)
        valid &= healthy
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
