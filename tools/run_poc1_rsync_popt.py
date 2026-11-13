#!/usr/bin/env python3
"""Rerun PoC 1 (rsync/popt) under each configuration (tracker item S2).

Every (configuration, attack) pair is one process. Raw stdout, stderr and the
exit status are written first; outcomes are then read from those files only.
Nothing is retried. An outcome is "rejected" only if the wrapper printed a
named rejection; a process that dies without one is "crashed".

Configurations (JH, 2026-11-13: the RLBox-only baseline keeps RLBox confinement,
and there is one SP3):
  rlbox_only   separate comparator build: RLBox confinement and T's bounded
               string copy, no InterSpec tracking, no selective copy
               (INTERSPEC_SP1=0, INTERSPEC_SP2=0)
  interspec    the one build with SP1, SP2 and SP3 on
"""

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

CONFIGS = {
    "rlbox_only": ("rlbox", {"INTERSPEC_SP1": "0", "INTERSPEC_SP2": "0"}),
    "interspec": ("extended", {"INTERSPEC_SP1": "1", "INTERSPEC_SP2": "1",
                               "INTERSPEC_SP3": "1"}),
}
ATTACKS = {
    "benign": {},
    "sp1_read_help_text": {"INTERSPEC_TEST_POC_FLAGS": "1"},
    "sp2_write_readonly_val": {"INTERSPEC_TEST_POC_FLAGS": "2"},
    "sp3_pointer_outside_sandbox": {"INTERSPEC_TEST_POC_FLAGS": "4"},
    "sp3_pointer_untracked_in_sandbox": {"INTERSPEC_TEST_FAULT": "2",
                                         "INTERSPEC_TEST_TARGET": "2"},
    "poc1_all_three": {"INTERSPEC_TEST_POC_FLAGS": "7"},
}


def classify(code, stdout, stderr):
    """Outcome fields derived from the retained output of one process."""
    reject = re.search(r"^INTERSPEC_REJECT reason=(.*)$", stderr, re.M)
    done = re.search(r"^T_OBSERVE stage=done .*g_slot=(\S+) readonly_val=(-?\d+) ", stdout, re.M)
    context = re.search(r"stage=context secret_help_in_u=(\d) secret_arg_in_u=(\d) "
                        r"readonly_val=(-?\d+)$", stdout, re.M)
    vals = re.findall(r"readonly_val=(-?\d+)", stdout)
    if reject:
        process = "rejected"
    elif code == 0 and done:
        process = "completed"
    elif code is not None and code < 0:
        process = "crashed"
    else:
        process = "failed"
    return {
        "exit": code,
        "signal": signal.Signals(-code).name if code is not None and code < 0 else None,
        "process": process,
        "rejection_reason": reject.group(1) if reject else None,
        "secret_in_u_memory": (context.group(1) == "1" or context.group(2) == "1")
        if context else None,
        "u_printed_secret": "descrip='SECRET_HELP'" in stderr,
        "t_readonly_val_last_seen": int(vals[-1]) if vals else None,
        "t_slot_value": done.group(1) if done else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extended", required=True, type=Path)
    parser.add_argument("--rlbox", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    drivers = {"extended": args.extended, "rlbox": args.rlbox}
    args.out.mkdir(parents=True)

    results = {}
    for config, (driver, switches) in CONFIGS.items():
        for attack, request in ATTACKS.items():
            name = f"{config}__{attack}"
            case = args.out / name
            case.mkdir()
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                   "INTERSPEC_POLICY_REPORT": "1", **switches, **request}
            (case / "env.json").write_text(json.dumps(env, indent=2, sort_keys=True) + "\n")
            (case / "driver.txt").write_text(f"{driver}\n")
            try:
                done = subprocess.run([str(drivers[driver])], env=env, timeout=120,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                code, out, err = done.returncode, done.stdout, done.stderr
            except subprocess.TimeoutExpired as expired:
                code, out, err = None, expired.stdout or b"", expired.stderr or b""
            (case / "stdout.txt").write_bytes(out)
            (case / "stderr.txt").write_bytes(err)
            (case / "exit_code.txt").write_text(f"{code}\n")

    # Second pass: read the retained files back and classify.
    for config in CONFIGS:
        for attack in ATTACKS:
            case = args.out / f"{config}__{attack}"
            raw_code = (case / "exit_code.txt").read_text().strip()
            code = None if raw_code == "None" else int(raw_code)
            results.setdefault(config, {})[attack] = classify(
                code, (case / "stdout.txt").read_text(errors="replace"),
                (case / "stderr.txt").read_text(errors="replace"))

    def pointer(config, attack):
        r = results[config][attack]
        return r["process"] + (f" ({r['rejection_reason']})" if r["rejection_reason"] else
                               f" ({r['signal']})" if r["signal"] else "")

    lines = ["| Configuration | U reads help text | T's `val` after U's write | "
             "Pointer outside sandbox | Untracked pointer in sandbox | PoC 1, all three |",
             "|---|---|---|---|---|---|"]
    for config in CONFIGS:
        r = results[config]
        lines.append(
            f"| {config} | {'yes' if r['sp1_read_help_text']['secret_in_u_memory'] else 'no'} | "
            f"{r['sp2_write_readonly_val']['t_readonly_val_last_seen']} | "
            f"{pointer(config, 'sp3_pointer_outside_sandbox')} | "
            f"{pointer(config, 'sp3_pointer_untracked_in_sandbox')} | "
            f"{pointer(config, 'poc1_all_three')} |")
    table = "\n".join(lines) + "\n"

    def effect(without, with_, attack, field):
        return results[without][attack][field] != results[with_][attack][field]

    effects = {
        "sp1": effect("rlbox_only", "interspec", "sp1_read_help_text", "secret_in_u_memory"),
        "sp2": effect("rlbox_only", "interspec", "sp2_write_readonly_val",
                      "t_readonly_val_last_seen"),
        "sp3_untracked_pointer": effect("rlbox_only", "interspec",
                                        "sp3_pointer_untracked_in_sandbox", "process"),
        "sp3_outside_pointer": effect("rlbox_only", "interspec",
                                      "sp3_pointer_outside_sandbox", "process"),
    }
    benign_ok = all(results[c]["benign"]["process"] == "completed" and
                    results[c]["benign"]["t_slot_value"] == "hello" and
                    results[c]["benign"]["t_readonly_val_last_seen"] == 42 for c in CONFIGS)
    summary = {"drivers_sha256": {k: hashlib.sha256(v.read_bytes()).hexdigest()
                                  for k, v in drivers.items()},
               "results": results, "effects": effects, "benign_ok": benign_ok,
               "crashes_counted_as_rejections": 0}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.out / "TABLE.md").write_text(table)
    print(table)
    for name, value in effects.items():
        print(f"{'EFFECT   ' if value else 'NO EFFECT'} {name}")
    print(f"benign_ok={benign_ok}")
    # Evidence collection succeeds if every case ran and the benign controls
    # hold. Whether each policy shows an effect is reported, not forced.
    return 0 if benign_ok else 1


if __name__ == "__main__":
    sys.exit(main())
