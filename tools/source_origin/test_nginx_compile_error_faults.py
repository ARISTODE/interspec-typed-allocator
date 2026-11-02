#!/usr/bin/env python3
"""Verify malformed sandbox PCRE error metadata is denied before Nginx uses it.

These deliberately injected U faults are security tests, never counted as
legitimate upstream application stack/global pointer occurrences.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess

CASES = {
    1: "malformed_extent",
    2: "malformed_termination",
    3: "malformed_offset",
    4: "malformed_text",
}


def no_core_dump():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run(work, out):
    binary = work / "bin" / "nginx-diagnostics"
    if not binary.is_file():
        raise RuntimeError("diagnostic Nginx binary missing: " + str(binary))
    out.mkdir(parents=True, exist_ok=True)
    conf = out / "invalid-pcre.conf"
    conf.write_text(
        'events { worker_connections 16; }\n'
        'http { server { listen 127.0.0.1:18080; '
        'location ~ "[" { return 200; } } }\n'
    )
    records = []
    for kind, reason in CASES.items():
        prefix = out / ("fault-kind-" + str(kind))
        prefix.mkdir(parents=True, exist_ok=True)
        (prefix / "logs").mkdir(exist_ok=True)
        env = dict(os.environ, LC_ALL="C",
                   INTERSPEC_NGINX_FAULT_PATH="3",
                   INTERSPEC_NGINX_FAULT_KIND=str(kind))
        result = subprocess.run(
            [str(binary), "-t", "-p", str(prefix.resolve()) + "/",
             "-c", str(conf.resolve())],
            env=env, capture_output=True, text=True,
            timeout=30, preexec_fn=no_core_dump,
        )
        marker = "INTERSPEC_REJECT boundary=nginx_pcre operation=compile_error reason=" + reason
        passed = result.returncode == -signal.SIGABRT and marker in result.stderr
        records.append({
            "fault_kind": kind,
            "expected_reason": reason,
            "returncode": result.returncode,
            "pass": passed,
            "stderr": result.stderr,
        })
        print(json.dumps({
            "fault_kind": kind, "pass": passed, "returncode": result.returncode,
            "expected_reason": reason,
        }, sort_keys=True))
    summary = {
        "schema": 1,
        "scope": "deliberate U corruption of registered error buffer metadata",
        "counts_as_original_application_pointer": False,
        "passed": sum(row["pass"] for row in records),
        "total": len(records),
        "results": records,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(conf.read_bytes()).hexdigest(),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    if summary["passed"] != summary["total"]:
        raise SystemExit("sandbox error metadata corruption was not fully rejected")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path,
                   default=Path("/tmp/interspec-nginx-deployment"))
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    run(args.work, args.out)


if __name__ == "__main__":
    main()
