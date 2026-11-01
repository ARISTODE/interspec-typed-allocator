#!/usr/bin/env python3
"""Native original-memcached runtime workload, with strict protocol parity.

The workload is diagnostic code and NEVER contributes pointer-origin call sites.
The traced binary uses linker --wrap with the upstream logger.c/items.c unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memcached_common import Client, Server


def exercise(binary: Path, out: Path, trace: Path | None):
    out.mkdir(parents=True, exist_ok=True)
    old = os.environ.get("INTERSPEC_ORIGINAL_SOURCE_TRACE")
    try:
        if trace is None:
            os.environ.pop("INTERSPEC_ORIGINAL_SOURCE_TRACE", None)
        else:
            os.environ["INTERSPEC_ORIGINAL_SOURCE_TRACE"] = str(trace.resolve())
        with Server(binary, out, "original-native", extra=()) as server:
            response = {}
            with Client(server.port) as client:
                response["version_ok"] = client.command(b"version").startswith(b"VERSION ")
                response["set"] = client.store(b"source-provenance", b"source-only")
                response["get"] = client.get(b"source-provenance")[b"source-provenance"]["data"]
                response["delete"] = client.command(b"delete source-provenance")
                response["miss"] = client.get(b"source-provenance")
                response["invalid"] = client.command(b"invalid-command")
            with Client(server.port, timeout=8) as watcher:
                response["watch"] = watcher.command(b"watch fetchers mutations deletions")
                with Client(server.port) as client:
                    response["watched_set"] = client.store(b"boundary-evidence", b"payload")
                    response["watched_get"] = client.get(b"boundary-evidence")[b"boundary-evidence"]["data"]
                    response["watched_delete"] = client.command(b"delete boundary-evidence")
                seen = set()
                for _ in range(16):
                    message = watcher.line().decode("utf-8", errors="replace").strip()
                    if "key=boundary-evidence " in message:
                        m = re.search(r"type=(\w+)", message)
                        if m:
                            seen.add(m.group(1))
                    if {"item_store", "item_get", "deleted"} <= seen:
                        break
                response["watch_event_types"] = sorted(seen)
            assert server.proc.poll() is None, "native memcached unexpectedly terminated"
        assert response["version_ok"]
        assert response["set"] == b"STORED\r\n"
        assert response["get"] == b"source-only"
        assert response["delete"] == b"DELETED\r\n"
        assert response["miss"] == {}
        assert response["invalid"] == b"ERROR\r\n"
        assert response["watch"] == b"OK\r\n"
        assert response["watched_set"] == b"STORED\r\n"
        assert response["watched_get"] == b"payload"
        assert response["watched_delete"] == b"DELETED\r\n"
        assert {"item_store", "item_get", "deleted"} <= set(response["watch_event_types"])
        return {k: v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v
                for k, v in response.items()}
    finally:
        if old is None:
            os.environ.pop("INTERSPEC_ORIGINAL_SOURCE_TRACE", None)
        else:
            os.environ["INTERSPEC_ORIGINAL_SOURCE_TRACE"] = old


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--traced", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    trace = args.output / "memcached-original-pointer-events.jsonl"
    assert not trace.exists(), f"refusing to append to existing trace: {trace}"
    baseline = exercise(args.baseline, args.output / "baseline", None)
    observed = exercise(args.traced, args.output / "traced", trace)
    assert baseline == observed, f"native behavior differs: {baseline!r} vs {observed!r}"
    assert trace.is_file() and trace.stat().st_size > 0, "no runtime pointer events"
    data = {
        "schema": 1,
        "scope": "unchanged-original-native-memcached-only",
        "source_origin_counting": "only records resolved to upstream logger.c/items.c by verifier",
        "parity": "pass",
        "observations": observed,
        "sha256": {
            "baseline_binary": hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
            "traced_binary": hashlib.sha256(args.traced.read_bytes()).hexdigest(),
            "raw_trace": hashlib.sha256(trace.read_bytes()).hexdigest(),
        },
    }
    (args.output / "native-parity.json").write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps({"parity": data["parity"], "checks": len(observed),
                      "raw_trace_sha256": data["sha256"]["raw_trace"]}))


if __name__ == "__main__":
    main()
