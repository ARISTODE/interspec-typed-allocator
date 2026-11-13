#!/usr/bin/env python3
"""Benign run of the complete rsync executable under the policy switches (I1).

The isolated rsync (popt inside RLBox wasm2c, no test hooks) and native rsync
from the same revision run the same commands on the same input tree. For every
switch configuration the isolated run must exit 0, report the configuration it
actually used, print the same stdout as native and produce the same destination
tree. All raw output is written before anything is compared; nothing is retried.

This is a functional check. Elapsed time is not recorded or reported.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Tracker "Done when" needs all_on. The others are the configurations that the
# per-policy measurements (P6) will use, so they must be functional as well.
CONFIGS = {
    "all_on": ("1", "1", "1"),
    "all_off": ("0", "0", "0"),
    "sp1_only": ("1", "0", "0"),
    "sp2_only": ("0", "1", "0"),
    "sp3_only": ("0", "0", "1"),
}
SP3_NAME = {"0": "off", "1": "full"}


def make_tree(src):
    (src / "nested" / "deep").mkdir(parents=True)
    (src / "input.txt").write_text("InterSpec policy switch benign run\n")
    (src / "nested" / "data.bin").write_bytes(
        b"".join(hashlib.sha256(bytes([i])).digest() for i in range(256)))
    (src / "nested" / "deep" / "empty").write_bytes(b"")
    (src / "nested" / "skip.tmp").write_text("excluded\n")
    (src / "large.txt").write_text("".join(f"line {i}\n" for i in range(20000)))
    for path in sorted(src.rglob("*")):
        os.utime(path, (1_700_000_000, 1_700_000_000))
    os.utime(src, (1_700_000_000, 1_700_000_000))


def tree_digest(root):
    entries = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append(["dir", rel])
        else:
            entries.append(["file", rel, hashlib.sha256(path.read_bytes()).hexdigest(),
                            int(path.stat().st_mtime)])
    return entries


def commands(src, dst, backup):
    return {
        "version": ["--backup-dir=" + str(backup), "--max-size=1M",
                    "--block-size=1024", "--version"],
        "dry_run": ["--dry-run", "-a", "-i", str(src) + "/", str(dst) + "/"],
        "sync": ["-a", "--checksum", "--exclude=*.tmp",
                 "--out-format=%n %l", str(src) + "/", str(dst) + "/"],
        "bad_option": ["--no-such-option"],
    }


def run_all(binary, env, work, record_dir):
    src, dst, backup = work / "src", work / "dst", work / "backup"
    src.mkdir(parents=True)
    dst.mkdir()
    backup.mkdir()
    make_tree(src)
    record_dir.mkdir(parents=True)
    result = {}
    for name, args in commands(src, dst, backup).items():
        done = subprocess.run([str(binary)] + args, env=env, cwd=work,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=300)
        (record_dir / f"{name}.stdout.txt").write_bytes(done.stdout)
        (record_dir / f"{name}.stderr.txt").write_bytes(done.stderr)
        (record_dir / f"{name}.exit_code.txt").write_text(f"{done.returncode}\n")
        result[name] = {"exit": done.returncode,
                        "stdout": done.stdout.decode(errors="replace"),
                        "stderr": done.stderr.decode(errors="replace")}
    result["src_tree"] = tree_digest(src)
    result["dst_tree"] = tree_digest(dst)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rsync", required=True, type=Path)
    parser.add_argument("--native", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True)
    # Input and destination trees live outside the retained evidence.
    scratch = Path(tempfile.mkdtemp(prefix="interspec-rsync-benign-"))
    base_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C"}

    native = run_all(args.native, base_env, scratch / "native", args.out / "native")
    summary = {"rsync_sha256": hashlib.sha256(args.rsync.read_bytes()).hexdigest(),
               "native_sha256": hashlib.sha256(args.native.read_bytes()).hexdigest(),
               "native_exits": {k: v["exit"] for k, v in native.items()
                                if isinstance(v, dict)},
               "configs": {}}
    expected_dst = [entry for entry in native["src_tree"]
                    if not entry[1].endswith(".tmp")]
    native_ok = (native["version"]["exit"] == 0 and native["dry_run"]["exit"] == 0
                 and native["sync"]["exit"] == 0 and native["bad_option"]["exit"] != 0
                 and native["dst_tree"] == expected_dst)
    summary["native_reference_ok"] = native_ok

    for name, (sp1, sp2, sp3) in CONFIGS.items():
        env = {**base_env, "INTERSPEC_SP1": sp1, "INTERSPEC_SP2": sp2,
               "INTERSPEC_SP3": sp3, "INTERSPEC_POLICY_REPORT": "1"}
        got = run_all(args.rsync, env, scratch / name, args.out / name)
        report = (f"INTERSPEC_POLICY boundary=rsync_popt sp1={sp1} sp2={sp2} "
                  f"sp3={SP3_NAME[sp3]}\n")
        checks = {}
        for command in ("version", "dry_run", "sync", "bad_option"):
            checks[f"{command}_exit_matches_native"] = (
                got[command]["exit"] == native[command]["exit"])
            # Paths differ only in the per-configuration scratch directory.
            checks[f"{command}_stdout_matches_native"] = (
                got[command]["stdout"].replace(str(scratch / name), "@")
                == native[command]["stdout"].replace(str(scratch / "native"), "@"))
            checks[f"{command}_reports_configuration"] = (
                got[command]["stderr"].count(report) == 1)
            checks[f"{command}_no_rejection"] = (
                "INTERSPEC_REJECT" not in got[command]["stderr"])
        checks["destination_tree_matches_native"] = got["dst_tree"] == native["dst_tree"]
        checks["destination_tree_matches_source"] = got["dst_tree"] == expected_dst
        summary["configs"][name] = {"passed": all(checks.values()), "checks": checks}
        print(f"{'PASS' if all(checks.values()) else 'FAIL'} rsync benign {name}")
        for check, ok in checks.items():
            if not ok:
                print(f"  failed {check}")

    summary["passed"] = native_ok and all(c["passed"] for c in summary["configs"].values())
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if not native_ok:
        print("FAIL native reference run")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
