#!/usr/bin/env python3
"""Native original Nginx/PCRE config checks, with identical input and parity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

VALID = """worker_processes 1;
error_log stderr notice;
events { worker_connections 16; }
http {
    server {
        listen 127.0.0.1:18080;
        location ~ "^example[0-9]+$" { return 204; }
    }
}
"""
INVALID = """worker_processes 1;
error_log stderr notice;
events { worker_connections 16; }
http {
    server {
        listen 127.0.0.1:18080;
        location ~ "[" { return 204; }
    }
}
"""


def normalized(data):
    # Nginx messages can contain a wall-clock timestamp and current pid.
    return re.sub(
        r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[\w+\] \d+#\d+: ",
        "<timestamp-and-pid> ", data)


def invoke(binary, prefix, conf, trace):
    env = dict(os.environ, LC_ALL="C")
    env.pop("INTERSPEC_NGINX_ORIGINAL_TRACE", None)
    if trace:
        env["INTERSPEC_NGINX_ORIGINAL_TRACE"] = str(trace.resolve())
    proc = subprocess.run([str(binary), "-t", "-p", str(prefix) + "/",
                           "-c", str(conf)], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=20)
    return {"exit_code": proc.returncode,
            "stdout_normalized": normalized(proc.stdout.decode(errors="replace")),
            "stderr_normalized": normalized(proc.stderr.decode(errors="replace"))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--traced", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    config_dir = args.output / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.output / "prefix"
    (prefix / "logs").mkdir(parents=True, exist_ok=True)
    for name, contents in (("valid", VALID), ("invalid", INVALID)):
        (config_dir / f"{name}.conf").write_text(contents)
    trace = args.output / "nginx-original-pointer-events.jsonl"
    assert not trace.exists(), f"refusing to append old trace: {trace}"
    cases = []
    for case in ("valid", "invalid"):
        cfg = (config_dir / f"{case}.conf").resolve()
        baseline = invoke(args.baseline, prefix.resolve(), cfg, None)
        traced = invoke(args.traced, prefix.resolve(), cfg, trace)
        assert baseline == traced, (case, baseline, traced)
        if case == "valid":
            assert baseline["exit_code"] == 0, baseline
        else:
            assert baseline["exit_code"] != 0, baseline
            assert "pcre_compile() failed" in baseline["stderr_normalized"], baseline
        cases.append({"case": case, **baseline})
    assert trace.exists() and trace.stat().st_size, "no Nginx PCRE call events"
    report = {
        "schema": 1, "scope": "pinned-native-nginx-pcre-error-and-success-configs",
        "parity": "pass", "cases": cases,
        "sha256": {
            "baseline_binary": hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
            "traced_binary": hashlib.sha256(args.traced.read_bytes()).hexdigest(),
            "raw_trace": hashlib.sha256(trace.read_bytes()).hexdigest(),
            "valid_config": hashlib.sha256(VALID.encode()).hexdigest(),
            "invalid_config": hashlib.sha256(INVALID.encode()).hexdigest(),
        },
    }
    (args.output / "native-parity.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"parity": "pass", "cases": len(cases),
                      "raw_trace_sha256": report["sha256"]["raw_trace"]}))


if __name__ == "__main__":
    main()
