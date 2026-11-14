#!/usr/bin/env python3
"""Rerun PoC 2 (nginx/libpcre, PCRE 8.45) under each configuration (tracker S3).

Every (configuration, attack) pair is one process of the nginx policy-switch
driver with a named-capture expression. Raw stdout, stderr and the exit status
are written first; outcomes are then read from those files only. Nothing is
retried. An outcome is "rejected" only if the wrapper printed a named
rejection; a process that dies without one is "crashed".

Configurations (JH, 2026-11-13: the RLBox-only baseline keeps RLBox
confinement, and there is one SP3):
  rlbox_only   RLBox-only bridge build on the untracked fault-test module: no
               InterSpec tracking or registry, no selective copy
               (INTERSPEC_SP1=0, INTERSPEC_SP2=0), sandbox confinement kept
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
    "interspec": ("interspec", {"INTERSPEC_SP1": "1", "INTERSPEC_SP2": "1",
                                "INTERSPEC_SP3": "1"}),
}
ATTACKS = {
    "benign": {},
    "sp1_read_output_vector": {"INTERSPEC_TEST_POC_FLAGS": "1"},
    "sp2_write_subject": {"INTERSPEC_TEST_POC_FLAGS": "2"},
    # The paper's PoC 2: name table pointer outside the sandbox.
    "sp3_name_table_outside_sandbox": {"INTERSPEC_NGINX_FAULT_PATH": "1",
                                       "INTERSPEC_NGINX_FAULT_KIND": "7"},
    "sp3_name_table_untracked_in_sandbox": {"INTERSPEC_NGINX_FAULT_PATH": "1",
                                            "INTERSPEC_NGINX_FAULT_KIND": "2"},
}
SUBJECT = "2f6974656d732f3132332f616c706861"


def classify(code, stdout, stderr):
    reject = re.search(r"^INTERSPEC_REJECT boundary=nginx_pcre operation=(\S+) reason=(\S+)$",
                       stderr, re.M)
    done = re.search(r"^T_OBSERVE stage=done$", stdout, re.M)
    executed = re.search(r"^T_OBSERVE stage=exec rc=(-?\d+) subject=([0-9a-f]+) captures=(\S*)$",
                         stdout, re.M)
    u_read = re.search(r"\[SP1\] sandbox read exec ovector\[0\]=0x([0-9a-f]+)$", stderr, re.M)
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
        "rejection": f"{reject.group(1)}: {reject.group(2)}" if reject else None,
        "u_read_t_vector_value": (u_read.group(1) == "5ec2e7") if u_read else None,
        "t_subject_unchanged": (executed.group(2) == SUBJECT) if executed else None,
        "t_captures": executed.group(3) if executed else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interspec", required=True, type=Path)
    parser.add_argument("--rlbox", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    drivers = {"interspec": args.interspec, "rlbox": args.rlbox}
    args.out.mkdir(parents=True)

    for config, (driver, switches) in CONFIGS.items():
        for attack, request in ATTACKS.items():
            case = args.out / f"{config}__{attack}"
            case.mkdir()
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                   "INTERSPEC_POLICY_REPORT": "1", **switches, **request}
            (case / "env.json").write_text(json.dumps(env, indent=2, sort_keys=True) + "\n")
            (case / "driver.txt").write_text(f"{driver}\n")
            try:
                done = subprocess.run([str(drivers[driver]), "named"], env=env, timeout=120,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                code, out, err = done.returncode, done.stdout, done.stderr
            except subprocess.TimeoutExpired as expired:
                code, out, err = None, expired.stdout or b"", expired.stderr or b""
            (case / "stdout.txt").write_bytes(out)
            (case / "stderr.txt").write_bytes(err)
            (case / "exit_code.txt").write_text(f"{code}\n")

    results = {}
    for config in CONFIGS:
        for attack in ATTACKS:
            case = args.out / f"{config}__{attack}"
            raw = (case / "exit_code.txt").read_text().strip()
            results.setdefault(config, {})[attack] = classify(
                None if raw == "None" else int(raw),
                (case / "stdout.txt").read_text(errors="replace"),
                (case / "stderr.txt").read_text(errors="replace"))

    def outcome(config, attack):
        r = results[config][attack]
        return r["process"] + (f" ({r['rejection']})" if r["rejection"] else
                               f" ({r['signal']})" if r["signal"] else "")

    lines = ["| Configuration | U reads T's output vector | T's subject after U's write | "
             "Name table pointer outside sandbox | Untracked name table pointer in sandbox |",
             "|---|---|---|---|---|"]
    for config in CONFIGS:
        r = results[config]
        lines.append(
            f"| {config} | {'yes' if r['sp1_read_output_vector']['u_read_t_vector_value'] else 'no'} | "
            f"{'unchanged' if r['sp2_write_subject']['t_subject_unchanged'] else 'changed'} | "
            f"{outcome(config, 'sp3_name_table_outside_sandbox')} | "
            f"{outcome(config, 'sp3_name_table_untracked_in_sandbox')} |")
    table = "\n".join(lines) + "\n"

    def effect(attack, field):
        return results["rlbox_only"][attack][field] != results["interspec"][attack][field]

    effects = {
        "sp1": effect("sp1_read_output_vector", "u_read_t_vector_value"),
        "sp2": effect("sp2_write_subject", "t_subject_unchanged"),
        "sp3_untracked_pointer": effect("sp3_name_table_untracked_in_sandbox", "process"),
        "sp3_outside_pointer": effect("sp3_name_table_outside_sandbox", "process"),
    }
    benign_ok = all(results[c]["benign"]["process"] == "completed" and
                    results[c]["benign"]["t_captures"] == "0-16,7-10,11-16" and
                    results[c]["benign"]["t_subject_unchanged"] for c in CONFIGS)
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
    # Collection succeeds if every case ran and the benign controls hold.
    # Whether each policy shows an effect is reported, not forced.
    return 0 if benign_ok else 1


if __name__ == "__main__":
    sys.exit(main())
