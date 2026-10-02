#!/usr/bin/env python3
"""Exercise actual server traffic, upstream tests, and source-corrupted U."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import traceback
from memcached_common import Client, Server


def normal(server, output):
    completed = []
    with Client(server.port) as c:
        assert c.store(b"alpha", b"value", flags=17) == b"STORED\r\n"
        assert c.get(b"alpha")[b"alpha"] == {"data": b"value", "flags": 17, "cas": None}
        completed.append("set_get_flags")
        assert c.store(b"alpha", b"no", command=b"add") == b"NOT_STORED\r\n"
        assert c.store(b"missing", b"no", command=b"replace") == b"NOT_STORED\r\n"
        assert c.store(b"alpha", b"new", command=b"replace") == b"STORED\r\n"
        completed.append("add_replace")
        token = c.get(b"alpha", command=b"gets")[b"alpha"]["cas"]
        assert c.store(b"alpha", b"cas", command=b"cas", cas=token + 1) == b"EXISTS\r\n"
        assert c.store(b"alpha", b"cas", command=b"cas", cas=token) == b"STORED\r\n"
        completed.append("cas")
        assert c.store(b"alpha", b"!", command=b"append") == b"STORED\r\n"
        assert c.store(b"alpha", b"!", command=b"prepend") == b"STORED\r\n"
        assert c.get(b"alpha")[b"alpha"]["data"] == b"!cas!"
        completed.append("append_prepend")
        assert c.store(b"counter", b"10") == b"STORED\r\n"
        assert c.command(b"incr counter 7") == b"17\r\n"
        assert c.command(b"decr counter 30") == b"0\r\n"
        completed.append("incr_decr")
        payload = bytes(range(256)) * 1024
        assert c.store(b"binary", payload) == b"STORED\r\n"
        assert c.get(b"binary")[b"binary"]["data"] == payload
        completed.append("binary_256k")
        assert set(c.get(b"alpha counter missing")) == {b"alpha", b"counter"}
        completed.append("multiget")
        assert c.command(b"touch alpha 60") == b"TOUCHED\r\n"
        assert c.command(b"delete alpha") == b"DELETED\r\n"
        assert c.command(b"delete alpha") == b"NOT_FOUND\r\n"
        completed.append("touch_delete")
        c.send(b"set fragmented 0 0 5\r\nhe")
        c.send(b"llo\r\n")
        assert c.line() == b"STORED\r\n"
        assert c.get(b"fragmented")[b"fragmented"]["data"] == b"hello"
        completed.append("fragmented_request")
        assert c.command(b"nonsense") == b"ERROR\r\n"
        assert c.command(b"incr counter invalid").startswith(b"CLIENT_ERROR")
        completed.append("invalid_commands")
        assert c.store(b"expired", b"gone", expiry=1) == b"STORED\r\n"
        time.sleep(2.05)
        assert not c.get(b"expired")
        completed.append("expiry")
        assert c.command(b"flush_all") == b"OK\r\n"
        assert not c.get(b"binary")
        completed.append("flush_all")

    # Real watcher traffic activates both worker and output bipbuffers.
    watcher = Client(server.port)
    assert watcher.command(b"watch fetchers mutations deletions") == b"OK\r\n"
    lines = []
    with Client(server.port) as c:
        assert c.store(b"evidence", b"payload") == b"STORED\r\n"
        assert c.get(b"evidence")[b"evidence"]["data"] == b"payload"
        assert c.command(b"delete evidence") == b"DELETED\r\n"
    expected_types = {"item_store", "item_get", "deleted"}
    seen = set()
    while not expected_types.issubset(seen) and len(lines) < 12:
        line = watcher.line().decode().strip()
        if "key=evidence " in line:
            lines.append(line)
            seen.add(re.search(r"type=(\w+)", line)[1])
    assert expected_types.issubset(seen), lines
    watcher.close()
    completed.append("watch_log_content")
    (output / "watch-records.json").write_text(json.dumps(lines, indent=2) + "\n")

    def worker(n):
        with Client(server.port) as c:
            for i in range(250):
                key = f"parallel-{n}-{i}".encode()
                value = hashlib.sha256(key).digest()
                assert c.store(key, value) == b"STORED\r\n"
                assert c.get(key)[key]["data"] == value
    with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(worker, range(4)))
    completed.append("concurrent_cache_2000_ops")

    # Repeated watcher teardown exercises release and sandbox destruction.
    for _ in range(25):
        with Client(server.port) as w:
            assert w.command(b"watch mutations") == b"OK\r\n"
    with Client(server.port) as c:
        assert c.command(b"version").startswith(b"VERSION ")
    completed.append("watcher_churn_25")
    assert server.proc.poll() is None
    return completed


def fault_case(server, mode):
    # Mutation can trigger on watcher greeting, worker write, worker read, or
    # watcher output. A rejection may race with successful cache responses.
    try:
        with Client(server.port, timeout=3) as watcher:
            assert watcher.command(b"watch fetchers mutations") == b"OK\r\n"
            with Client(server.port, timeout=3) as client:
                assert client.store(b"fault-key", b"value") == b"STORED\r\n"
                assert client.get(b"fault-key")[b"fault-key"]["data"] == b"value"
            for _ in range(10):
                if b"key=fault-key " in watcher.line(): break
            if mode == 5:
                assert server.proc.poll() is None
                return
            server.proc.wait(timeout=4)
    except (EOFError, ConnectionError, OSError):
        if mode == 5: raise
    if mode != 5:
        server.proc.wait(timeout=5)
        assert server.proc.returncode == -6, server.proc.returncode


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, default=Path("/tmp/interspec-memcached-deployment"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--skip-upstream", action="store_true")
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    binaries = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((args.work / "bin").glob("memcached-*"))}

    def run(name, fn):
        start = time.monotonic()
        try:
            details = fn() or {}
            row = {"case": name, "pass": True, "seconds": time.monotonic() - start, **details}
        except Exception:
            row = {"case": name, "pass": False, "seconds": time.monotonic() - start, "error": traceback.format_exc()}
        rows.append(row)
        print(json.dumps(row), flush=True)
        (args.out / "summary.json").write_text(json.dumps({"passed": sum(r["pass"] for r in rows), "total": len(rows), "binary_sha256": binaries, "cases": rows}, indent=2) + "\n")

    for variant in ("native", "rlbox-only", "tracked-no-check", "interspec", "diagnostics"):
        def test(variant=variant):
            out = args.out / variant
            with Server(args.work / "bin" / f"memcached-{variant}", out, "normal", trace=variant == "diagnostics") as server:
                checks = normal(server, out)
            text = server.logpath.read_text()
            assert "INTERSPEC_REJECT" not in text
            if variant == "diagnostics":
                for op in ("check", "request", "peek_all", "poll", "release"):
                    # request emits runtime check; only copied read ops have names.
                    if op != "request": assert f"event={op} " in text, op
            elif variant != "native": assert "INTERSPEC seq=" not in text
            return {"checks": checks, "checks_passed": len(checks)}
        run(f"normal-{variant}", test)

    for role in (1, 2):
        for target in (1, 2, 3):
            for mode, reason in ((1, "wrong_type"), (2, "untracked"), (3, "untracked"), (4, "out_of_bounds")):
                def test(role=role, target=target, mode=mode, reason=reason):
                    name = f"fault-r{role}-t{target}-m{mode}"
                    with Server(args.work / "bin/memcached-diagnostics", args.out / "faults", name,
                                trace=True, fault={"role": role, "target": target, "fault": mode}) as server:
                        fault_case(server, mode)
                    text = server.logpath.read_text()
                    assert f"mode={mode} target={target}" in text
                    assert f"reason={reason}" in text, text[-1500:]
                    return {"role": role, "target": target, "mode": mode, "reason": reason, "exit_code": server.proc.returncode}
                run(f"fault-r{role}-t{target}-m{mode}", test)

    for role, mode in ((1, 5), (2, 5), (1, 6)):
        def test(role=role, mode=mode):
            name = f"control-r{role}-m{mode}"
            with Server(args.work / "bin/memcached-diagnostics", args.out / "faults", name,
                        trace=True, fault={"role": role, "target": 2, "fault": mode}) as server:
                fault_case(server, mode)
            text = server.logpath.read_text()
            assert f"mode={mode} target=2" in text
            if mode == 5: assert "INTERSPEC_REJECT" not in text
            else: assert "reason=malformed_record" in text
            return {"mode": mode, "role": role, "outcome": "accepted_same_type" if mode == 5 else "rejected_malformed_record"}
        run(f"control-r{role}-m{mode}", test)

    if not args.skip_upstream:
        for variant in ("native", "interspec"):
            def test(variant=variant):
                directory = args.work / f"upstream-tests-{variant}"
                directory.mkdir(exist_ok=True)
                # Keep upstream test assertions intact. Select loopback TCP in
                # their copied launcher, since managed hosts may block Unix
                # sockets. Apply the identical transport change to both builds.
                if (directory / "t").is_symlink(): (directory / "t").unlink()
                shutil.copytree(args.work / "upstream/t", directory / "t", dirs_exist_ok=True)
                harness = directory / "t/lib/MemcachedTest.pm"
                source = harness.read_text()
                marker = '    $args .= " -o relaxed_privileges";'
                assert source.count(marker) == 1
                harness.write_text(source.replace(marker, marker + '\n    $args .= " -l 127.0.0.1 -U 0" unless $args =~ /-l /;', 1))
                if not (directory / "timedrun").exists(): (directory / "timedrun").symlink_to(args.work / "native/timedrun")
                shutil.copyfile(args.work / "bin" / f"memcached-{variant}-debug", directory / "memcached-debug")
                os.chmod(directory / "memcached-debug", 0o755)
                tests = ["t/watcher.t", "t/watcher_connid.t", "t/basic.t"]
                # Only select upstream tests present at the pinned revision.
                tests = [t for t in tests if (directory / t).is_file()]
                with (args.out / f"upstream-{variant}.log").open("wb") as log:
                    proc = subprocess.run(["prove", "-v", *tests], cwd=directory, stdout=log, stderr=subprocess.STDOUT, timeout=180)
                assert proc.returncode == 0, f"see upstream-{variant}.log"
                return {"tests": tests, "transport": "loopback_tcp", "test_assertions": "unmodified", "launcher_sha256": hashlib.sha256(harness.read_bytes()).hexdigest()}
            run(f"upstream-{variant}", test)
    if not all(r["pass"] for r in rows): raise SystemExit(1)


if __name__ == "__main__": main()
