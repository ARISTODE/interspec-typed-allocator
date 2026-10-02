#!/usr/bin/env python3
"""Capture actual application behavior and trusted rejection evidence.

Requires the test build produced by INTERSPEC_DIAGNOSTICS=1
INTERSPEC_FAULT_TESTS=1 scripts/run_rlbox_wasm2c_poc.sh. Never enables a
validation bypass. Fault modes change only U's behavior in a fixed executable.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import signal
import stat
import subprocess
import tempfile
from datetime import datetime, timezone


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records(text):
    return [dict(item.split("=", 1) for item in line.split()[1:])
            for line in text.splitlines() if line.startswith("INTERSPEC ")]


def snapshot(root):
    result = {}
    groups = {}
    for path in sorted(root.rglob("*")):
        st = path.lstat()
        name = str(path.relative_to(root))
        item = {"mode": stat.S_IMODE(st.st_mode), "uid": st.st_uid, "gid": st.st_gid}
        if path.is_symlink():
            item.update(kind="symlink", target=os.readlink(path))
        elif path.is_dir():
            item.update(kind="directory")
        else:
            item.update(kind="file", size=st.st_size, sha256=sha256(path), mtime_ns=st.st_mtime_ns)
            groups.setdefault((st.st_dev, st.st_ino), []).append(name)
        result[name] = item
    for names in groups.values():
        if len(names) > 1:
            for name in names:
                result[name]["hardlink_group"] = names
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, default=Path("/tmp/interspec-rlbox-wasm2c"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = args.work.resolve()
    binaries = {"integrated": work / "rsync-interspec", "native": work / "rsync-native",
                "canary": work / "copyback-canary", "smoke": work / "p9b-wasm-smoke"}
    for binary in binaries.values():
        if not binary.is_file():
            raise SystemExit(f"Missing test binary: {binary}")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    summary = {"utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
               "binaries": {k: {"path": str(v), "sha256": sha256(v)} for k, v in binaries.items()},
               "cases": [], "commands": []}

    def run(name, binary, arguments=(), mode=0, target=1):
        env = {**os.environ, "INTERSPEC_TRACE": "1", "INTERSPEC_TEST_FAULT": str(mode),
               "INTERSPEC_TEST_TARGET": str(target)}
        env.pop("INTERSPEC_TRACE_DUMP", None)
        command = [str(binaries[binary]), *map(str, arguments)]
        completed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
        (out / f"{name}.stdout").write_text(completed.stdout)
        (out / f"{name}.stderr").write_text(completed.stderr)
        recs = records(completed.stderr)
        summary["commands"].append({"name": name, "command": command, "fault_mode": mode,
                                    "fault_target": target, "returncode": completed.returncode,
                                    "events": dict(Counter(r["event"] for r in recs)),
                                    "results": dict(Counter(r["result"] for r in recs))})
        return completed, recs

    def case(name, passed, **details):
        row = {"name": name, "pass": bool(passed), **details}
        summary["cases"].append(row)
        print(json.dumps(row), flush=True)

    with tempfile.TemporaryDirectory(prefix="interspec-sp3-data-") as temporary:
        data = Path(temporary)
        src = data / "src"
        src.mkdir()
        (src / "nested directory").mkdir()
        (src / "empty-directory").mkdir()
        payloads = {"hello.txt": b"InterSpec application transfer\n", "empty": b"",
                    "binary.bin": bytes(range(256)) * 1024, "large.bin": b"L" * (2 * 1024 * 1024),
                    "nested directory/unicode-\u03bb.txt": "Unicode path and payload \u03bb\n".encode(),
                    "executable.sh": b"#!/bin/sh\nprintf 'ok\\n'\n"}
        for name, content in payloads.items():
            (src / name).write_bytes(content)
        (src / "executable.sh").chmod(0o755)
        os.link(src / "hello.txt", src / "hardlink.txt")
        os.symlink("hello.txt", src / "symlink")
        for path in [src, *src.rglob("*")]:
            os.utime(path, ns=(1700000000000000000, 1700000000000000000), follow_symlinks=False)
        source_manifest = snapshot(src)
        (out / "source-manifest.json").write_text(json.dumps(source_manifest, indent=2))
        case_details = {}

        for workload, extra in [("archive_transfer", []), ("size_filter", ["--max-size=1M"]),
                                ("dry_run", ["--dry-run", "--itemize-changes"])]:
            manifests = {}
            runs = {}
            destinations = {}
            for kind in ("native", "integrated"):
                dst = data / f"{workload}-{kind}"
                dst.mkdir()
                destinations[kind] = dst
                runs[kind], events = run(f"{workload}-{kind}", kind,
                    ["-aH", "--checksum", "--block-size=1024", *extra, f"{src}/", f"{dst}/"])
                manifests[kind] = snapshot(dst)
                (out / f"{workload}-{kind}.manifest.json").write_text(json.dumps(manifests[kind], indent=2))
            expected = dict(source_manifest)
            if workload == "size_filter":
                del expected["large.bin"]
            if workload == "dry_run":
                expected = {}
            pass_conditions = [p.returncode == 0 for p in runs.values()]
            pass_conditions += [manifests["native"] == manifests["integrated"] == expected,
                                "INTERSPEC_REJECT" not in runs["integrated"].stderr,
                                any(r["event"] == "remaining_bytes" for r in records(runs["integrated"].stderr))]
            if workload == "dry_run":
                pass_conditions.append(runs["native"].stdout == runs["integrated"].stdout)
            case(workload, all(pass_conditions), entries=len(manifests["integrated"]),
                 regular_files=sum(e["kind"] == "file" for e in manifests["integrated"].values()),
                 returncodes={k: p.returncode for k, p in runs.items()}, manifests_equal=manifests["native"] == manifests["integrated"])
            case_details[workload] = destinations

        # Update, delete, and retain previous content in backup directories.
        (src / "hello.txt").write_bytes(b"Changed source content for update test\n")
        os.utime(src / "hello.txt", ns=(1700000002000000000, 1700000002000000000))
        (src / "binary.bin").unlink()
        update_manifests, backup_manifests, returncodes = {}, {}, {}
        for kind in ("native", "integrated"):
            backup = data / f"backup-{kind}"
            backup.mkdir()
            dst = case_details["archive_transfer"][kind]
            p, _ = run(f"update_backup-{kind}", kind,
                       ["-aH", "--checksum", "--delete", "--backup", f"--backup-dir={backup}",
                        f"{src}/", f"{dst}/"])
            returncodes[kind] = p.returncode
            update_manifests[kind] = snapshot(dst)
            backup_manifests[kind] = snapshot(backup)
            (out / f"update-{kind}.manifest.json").write_text(json.dumps(update_manifests[kind], indent=2))
            (out / f"backup-{kind}.manifest.json").write_text(json.dumps(backup_manifests[kind], indent=2))
        case("update_delete_backup", all(rc == 0 for rc in returncodes.values()) and
             update_manifests["native"] == update_manifests["integrated"] == snapshot(src) and
             backup_manifests["native"] == backup_manifests["integrated"] and bool(backup_manifests["integrated"]),
             returncodes=returncodes, backup_entries=len(backup_manifests["integrated"]))

        for name, arguments in [("invalid_numeric_option", ["--block-size=not-a-size", "--version"]),
                                ("unknown_option", ["--interspec-option-does-not-exist"])]:
            normal, _ = run(name + "-native", "native", arguments)
            protected, _ = run(name + "-integrated", "integrated", arguments)
            case(name, normal.returncode == protected.returncode != 0 and
                 "INTERSPEC_REJECT" not in protected.stderr,
                 returncodes={"native": normal.returncode, "integrated": protected.returncode})

        # Every target uses a real file transfer workload with an empty destination.
        # The target selects a real popt return, option slot, or positional argument.
        for target in (1, 2, 3):
            for mode, expected in [(1, "wrong_type"), (2, "untracked"), (3, "untracked"),
                                   (4, "unterminated_string"), (5, "copied")]:
                name = f"fault-target{target}-mode{mode}"
                dst = data / name
                dst.mkdir()
                p, recs = run(name, "integrated",
                    ["-aH", "--block-size=1024", "--max-size=1M", f"{src}/", f"{dst}/"], mode, target)
                matches = re.findall(r"FAULT_INJECTION mode=(\d+) target=(\d+) original=(0x[0-9a-f]+) replacement=(0x[0-9a-f]+)", p.stderr)
                reached = bool(matches)
                original = int(matches[0][2], 16) if reached else None
                pointer = int(matches[0][3], 16) if reached else None
                after_injection = records(p.stderr.split("FAULT_INJECTION", 1)[1]) if reached else []
                before_injection = records(p.stderr.split("FAULT_INJECTION", 1)[0])
                checked = [r for r in after_injection if int(r["ptr"], 16) == pointer and r["event"] == "copy_checked"]
                matching = any(r["result"] == expected for r in checked)
                copied = any(r["result"] == "copied" for r in checked)
                released = any(r["event"] == "release" and int(r["ptr"], 16) == pointer
                               and r["result"] == "ok" for r in before_injection)
                if mode == 5:
                    expected_tree = snapshot(src)
                    expected_tree.pop("large.bin", None)
                    passed = reached and pointer != original and matching and copied and p.returncode == 0 and snapshot(dst) == expected_tree
                else:
                    passed = reached and matching and not copied and p.returncode == -signal.SIGABRT and not snapshot(dst) and "INTERSPEC_REJECT" in p.stderr
                    if mode == 3:
                        passed = passed and released
                case(name, passed, expected=expected, returncode=p.returncode,
                     injection_reached=reached, returned_pointer=hex(pointer) if pointer else None,
                     matching_trusted_decision=matching, copied= copied, prior_release= released,
                     destination_entries=len(snapshot(dst)))

    for mode in (0, 6):
        p, _ = run(f"copyback-mode{mode}", "canary", mode=mode)
        bindings = re.findall(r"INTERSPEC_BINDING event=(bind|copyback) slot=(\d+) destination=(0x[0-9a-f]+)", p.stderr)
        bound = {slot: addr for event, slot, addr in bindings if event == "bind"}
        copies = [(slot, addr) for event, slot, addr in bindings if event == "copyback"]
        passed = p.returncode == 0 and "copyback_canary=pass" in p.stdout and bool(copies) and all(bound.get(slot) == addr for slot, addr in copies)
        if mode:
            passed = passed and "FAULT_INJECTION mode=6" in p.stderr
        case(f"copyback-mode{mode}", passed, returncode=p.returncode,
             fixed_destination=all(bound.get(slot) == addr for slot, addr in copies), stdout=p.stdout.strip())

    p, _ = run("shadow_refresh", "canary", ["refresh"])
    case("shadow_refresh", p.returncode == 0 and "shadow_refresh=pass" in p.stdout,
         returncode=p.returncode, stdout=p.stdout.strip())

    p, recs = run("wasm_boundary_smoke", "smoke")
    decisions = {r["result"] for r in recs if r["event"] == "check"}
    case("wasm_boundary_smoke", p.returncode == 0 and {"ok", "wrong_type", "untracked", "out_of_bounds"} <= decisions,
         returncode=p.returncode, observed_check_results=sorted(decisions),
         scope="real sandbox allocations with a boundary driver, not a complete application extent attack")
    summary["passed"] = sum(row["pass"] for row in summary["cases"])
    summary["total"] = len(summary["cases"])
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"RESULT {summary['passed']}/{summary['total']} passed")
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
