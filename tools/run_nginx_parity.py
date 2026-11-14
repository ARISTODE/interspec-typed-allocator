#!/usr/bin/env python3
"""Run the rebuilt nginx/PCRE 8.45 parity set (tracker item I4): 104 responses.

Four release variants (native, rlbox-only, tracked-no-check, interspec) x 13
requests x forward and reverse order. Each order uses one persistent
connection. Every raw response is saved before anything is compared; status and
body must equal the hand-written expectation in evaluation/parity/nginx/
cases.json. Per variant the version output, a configuration syntax check and
the server's exit status are also kept. Nothing is retried; no timing is used.

This set is rebuilt from the description of the Stage 13 run. It is not the
original Stage 13 corpus, which is not in this repository.
"""

import argparse
import grp
import hashlib
import json
import os
import pwd
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

VARIANTS = ("native", "rlbox-only", "tracked-no-check", "interspec")


def read_response(sock, pending):
    """One HTTP/1.1 response with Content-Length from a keep-alive socket."""
    while b"\r\n\r\n" not in pending:
        chunk = sock.recv(65536)
        if not chunk:
            raise RuntimeError("connection closed before headers")
        pending += chunk
    head, rest = pending.split(b"\r\n\r\n", 1)
    length = None
    for line in head.split(b"\r\n")[1:]:
        name, _, value = line.partition(b":")
        if name.strip().lower() == b"content-length":
            length = int(value.strip())
    if length is None:
        raise RuntimeError("response without Content-Length")
    while len(rest) < length:
        chunk = sock.recv(65536)
        if not chunk:
            raise RuntimeError("connection closed inside body")
        rest += chunk
    return head + b"\r\n\r\n" + rest[:length], rest[length:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    cases = json.loads((args.corpus / "cases.json").read_text())["cases"]
    assert len(cases) == 13
    template = (args.corpus / "nginx.conf.template").read_text()
    user = (f"user {pwd.getpwuid(os.getuid()).pw_name} {grp.getgrgid(os.getgid()).gr_name};"
            if os.getuid() == 0 else "")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C",
           "INTERSPEC_SP1": "1", "INTERSPEC_SP2": "1", "INTERSPEC_SP3": "1",
           "INTERSPEC_POLICY_REPORT": "1"}
    args.out.mkdir(parents=True)
    out = args.out.resolve()

    for variant in VARIANTS:
        binary = args.work / "bin" / f"nginx-{variant}"
        directory = out / variant
        (directory / "logs").mkdir(parents=True)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        conf = directory / "nginx.conf"
        conf.write_text(template.replace("@USER@", user).replace("@DIR@", str(directory))
                        .replace("@PORT@", str(port)))
        base = [str(binary), "-p", str(directory) + "/", "-c", str(conf)]
        for name, extra in (("version", ["-V"]), ("syntax", ["-t"])):
            done = subprocess.run(base + extra, env=env, capture_output=True, timeout=60)
            (directory / f"{name}.stdout.txt").write_bytes(done.stdout)
            (directory / f"{name}.stderr.txt").write_bytes(done.stderr)
            (directory / f"{name}.exit_code.txt").write_text(f"{done.returncode}\n")
        with (directory / "server.stderr.txt").open("wb") as log:
            server = subprocess.Popen(base, env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 20
                while True:
                    try:
                        socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                        break
                    except OSError:
                        if server.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError(f"{variant}: server did not start")
                        time.sleep(0.05)
                for order, sequence in (("forward", cases), ("reverse", cases[::-1])):
                    (directory / order).mkdir()
                    with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
                        pending = b""
                        for index, case in enumerate(sequence):
                            sock.sendall(f"GET {case['path']} HTTP/1.1\r\nHost: {case['host']}\r\n"
                                         "Connection: keep-alive\r\n\r\n".encode())
                            raw, pending = read_response(sock, pending)
                            (directory / order / f"{index:02d}-{case['name']}.http").write_bytes(raw)
            finally:
                if server.poll() is None:
                    server.send_signal(signal.SIGQUIT)
                try:
                    code = server.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    server.kill()
                    code = server.wait()
                (directory / "server.exit_code.txt").write_text(f"{code}\n")

    # Second pass: read the saved files back and compare.
    rows, failures = [], 0
    variants = {}
    for variant in VARIANTS:
        directory = out / variant
        log = (directory / "server.stderr.txt").read_text(errors="replace")
        checks = {
            "version_exit_zero": (directory / "version.exit_code.txt").read_text().strip() == "0",
            "syntax_exit_zero": (directory / "syntax.exit_code.txt").read_text().strip() == "0",
            "server_exit_zero": (directory / "server.exit_code.txt").read_text().strip() == "0",
            "no_rejection": "INTERSPEC_REJECT" not in log and "INTERSPEC_ERROR" not in log,
        }
        if variant == "interspec":
            checks["reports_all_on"] = "INTERSPEC_POLICY boundary=nginx_pcre sp1=1 sp2=1 sp3=full" in log
        variants[variant] = checks
        failures += not all(checks.values())
        for order, sequence in (("forward", cases), ("reverse", cases[::-1])):
            for index, case in enumerate(sequence):
                raw = (directory / order / f"{index:02d}-{case['name']}.http").read_bytes()
                head, _, body = raw.partition(b"\r\n\r\n")
                status = int(head.split(b" ", 2)[1])
                ok = status == case["status"] and body == case["body"].encode()
                failures += not ok
                rows.append({"variant": variant, "order": order, "case": case["name"],
                             "status": status, "body": body.decode(errors="replace"),
                             "passed": ok})
                if not ok:
                    print(f"FAIL {variant} {order} {case['name']}: {status} {body!r}")
    for variant, checks in variants.items():
        for name, ok in checks.items():
            if not ok:
                print(f"FAIL {variant}: {name}")
    assert len(rows) == 104
    summary = {"responses": len(rows), "responses_passed": sum(r["passed"] for r in rows),
               "variants": variants,
               "binaries_sha256": {v: hashlib.sha256((args.work / "bin" / f"nginx-{v}").read_bytes()).hexdigest()
                                   for v in VARIANTS},
               "cases_sha256": hashlib.sha256((args.corpus / "cases.json").read_bytes()).hexdigest(),
               "rows": rows}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"nginx parity: {summary['responses_passed']}/{summary['responses']} responses matched")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
