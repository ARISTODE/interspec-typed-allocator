#!/usr/bin/env python3
"""Run the per-policy switch tests for one registry boundary (tracker I1 to I4).

Each case starts the boundary's test driver once, in a fresh process, with one
setting of the INTERSPEC_SP1 / INTERSPEC_SP2 / INTERSPEC_SP3 switches and one
requested U misbehavior. Raw stdout, stderr and the exit status of every case
are written before any expectation is evaluated. Nothing is retried and an
existing output directory is never reused.

A switch test is a pair (or triple) of cases that differ only in the switch
under test. It passes only if the cases on both sides behave as declared, so a
switch that changes nothing fails.
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

ALL_ON = {"INTERSPEC_SP1": "1", "INTERSPEC_SP2": "1", "INTERSPEC_SP3": "1"}


def switches(**overrides):
    env = dict(ALL_ON)
    for key, value in overrides.items():
        env["INTERSPEC_" + key.upper()] = value
    return env


def policy_line(boundary, env):
    sp3 = {"0": "off", "1": "full", "domain": "domain"}[env["INTERSPEC_SP3"]]
    return (rf"^INTERSPEC_POLICY boundary={boundary} sp1={env['INTERSPEC_SP1']} "
            rf"sp2={env['INTERSPEC_SP2']} sp3={sp3}$")


REJECT = signal.SIGABRT

# memcached/bipbuffer driver: the 16-byte record "T_RECORD_0123456" in hex.
MC_RECORD = "545f5245434f52445f30313233343536"
MC_BENIGN_OFFER = r"^T_OBSERVE stage=offer written=16 record=" + MC_RECORD + "$"
MC_BENIGN_PEEK = r"^T_OBSERVE stage=peek_all size=16 data=" + MC_RECORD + "$"
MC_FAULT = {"INTERSPEC_TEST_FAULT": "2", "INTERSPEC_TEST_TARGET": "2",
            "INTERSPEC_TEST_ROLE": "1"}

# Each case: switch settings, test-only U behavior, and what must be observed.
# "exit" is a return code; a negative value is the signal that ended the process.
BOUNDARIES = {
    "rsync_popt": {
        "tests": {
            "sp1": ["sp1_off_u_reads", "sp1_on_u_reads"],
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            "sp3": ["sp3_off_bad_pointer", "sp3_domain_bad_pointer",
                    "sp3_on_bad_pointer"],
            "benign": ["benign_all_on", "benign_all_off"],
        },
        "cases": {
            # SP1: U reads the help-text fields of option "set".
            "sp1_off_u_reads": {
                "env": {**switches(sp1="0"), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "exit": 0,
                "stdout": [r"stage=context secret_help_in_u=1 secret_arg_in_u=1 "],
                "stderr": [r"\[SP1\] sandbox read option='set' "
                           r"descrip='SECRET_HELP' argDescrip='SECRET_ARG'"],
            },
            "sp1_on_u_reads": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "exit": 0,
                "stdout": [r"stage=context secret_help_in_u=0 secret_arg_in_u=0 ",
                           r"stage=done rc=-1 g_slot=hello readonly_val=42 "
                           r"set_descrip=SECRET_HELP set_arg_descrip=SECRET_ARG"],
                "stderr": [r"\[SP1\] sandbox read option='set' "
                           r"descrip='\(null\)' argDescrip='\(null\)'"],
            },
            # SP2: U overwrites val of option "readonly" in its copy.
            "sp2_off_u_writes": {
                "env": {**switches(sp2="0"), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "exit": 0,
                "stdout": [r"stage=context .*readonly_val=1337$",
                           r"stage=done rc=-1 g_slot=hello readonly_val=1337 "],
                "stderr": [r"\[SP2\] sandbox mutated option='readonly' "
                           r"field=val old=42 new=1337"],
            },
            "sp2_on_u_writes": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "exit": 0,
                "stdout": [r"stage=context .*readonly_val=42$",
                           r"stage=done rc=-1 g_slot=hello readonly_val=42 "],
                "stdout_absent": [r"readonly_val=1337"],
                "stderr": [r"\[SP2\] sandbox mutated option='readonly' "
                           r"field=val old=42 new=1337"],
            },
            # SP3: U returns an untracked heap copy as the "set" string slot.
            "sp3_off_bad_pointer": {
                "env": {**switches(sp3="0"), "INTERSPEC_TEST_FAULT": "2",
                        "INTERSPEC_TEST_TARGET": "2"},
                "exit": 0,
                "stdout": [r"stage=done rc=-1 g_slot=hello readonly_val=42 "],
                "stderr": [r"^FAULT_INJECTION mode=2 target=2 "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_domain_bad_pointer": {
                "env": {**switches(sp3="domain"), "INTERSPEC_TEST_FAULT": "2",
                        "INTERSPEC_TEST_TARGET": "2"},
                "exit": 0,
                "stdout": [r"stage=done rc=-1 g_slot=hello readonly_val=42 "],
                "stderr": [r"^FAULT_INJECTION mode=2 target=2 "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_on_bad_pointer": {
                "env": {**switches(), "INTERSPEC_TEST_FAULT": "2",
                        "INTERSPEC_TEST_TARGET": "2"},
                # The bridge's deliberate fail-stop: a named rejection, then abort.
                "exit": -REJECT,
                "stdout_absent": [r"stage=done", r"g_slot=hello"],
                "stderr": [r"^FAULT_INJECTION mode=2 target=2 ",
                           r"^INTERSPEC_REJECT reason=InterSpec rejected popt char "
                           r"pointer: untracked$"],
            },
            "benign_all_on": {
                "env": switches(),
                "exit": 0,
                "stdout": [r"stage=context secret_help_in_u=0 secret_arg_in_u=0 "
                           r"readonly_val=42$",
                           r"stage=next rc=42 readonly_val=42$",
                           r"stage=done rc=-1 g_slot=hello readonly_val=42 "
                           r"set_descrip=SECRET_HELP set_arg_descrip=SECRET_ARG$"],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_off": {
                "env": switches(sp1="0", sp2="0", sp3="0"),
                "exit": 0,
                "stdout": [r"stage=next rc=42 readonly_val=42$",
                           r"stage=done rc=-1 g_slot=hello readonly_val=42 "
                           r"set_descrip=SECRET_HELP set_arg_descrip=SECRET_ARG$"],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
        },
    },
    "memcached_bipbuffer": {
        "tests": {
            "sp1": ["sp1_off_u_reads", "sp1_on_u_reads"],
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            "sp3": ["sp3_off_bad_pointer", "sp3_domain_bad_pointer",
                    "sp3_on_bad_pointer"],
            "benign": ["benign_all_on", "benign_all_off"],
        },
        "cases": {
            # SP1: U reads the value handed to it for the length out-parameter
            # of bipbuf_peek_all. T's value before the call is 0x5ec2e7.
            "sp1_off_u_reads": {
                "env": {**switches(sp1="0"), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "exit": 0,
                "stdout": [MC_BENIGN_PEEK, r"^T_OBSERVE stage=done$"],
                "stderr": [r"\[SP1\] sandbox read peek_all len_in=0x5ec2e7$"],
            },
            "sp1_on_u_reads": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "exit": 0,
                "stdout": [MC_BENIGN_PEEK, r"^T_OBSERVE stage=done$"],
                "stderr": [r"\[SP1\] sandbox read peek_all len_in=0x0$"],
                "stderr_absent": [r"5ec2e7"],
            },
            # SP2: U overwrites its copy of the data T passed to bipbuf_offer.
            "sp2_off_u_writes": {
                "env": {**switches(sp2="0"), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "exit": 0,
                "stdout": [r"^T_OBSERVE stage=offer written=16 record=ab" + MC_RECORD[2:] + "$",
                           MC_BENIGN_PEEK, r"^T_OBSERVE stage=done$"],
                "stderr": [r"\[SP2\] sandbox mutated offer data byte=0 old=0x54 new=0xab$"],
            },
            "sp2_on_u_writes": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "exit": 0,
                "stdout": [MC_BENIGN_OFFER, MC_BENIGN_PEEK, r"^T_OBSERVE stage=done$"],
                "stderr": [r"\[SP2\] sandbox mutated offer data byte=0 old=0x54 new=0xab$"],
            },
            # SP3: U returns an untracked heap copy from bipbuf_peek_all.
            "sp3_off_bad_pointer": {
                "env": {**switches(sp3="0"), **MC_FAULT},
                "exit": 0,
                "stdout": [MC_BENIGN_PEEK, r"^T_OBSERVE stage=done$"],
                "stderr": [r"^FAULT_INJECTION boundary=memcached_bipbuffer mode=2 target=2 "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_domain_bad_pointer": {
                "env": {**switches(sp3="domain"), **MC_FAULT},
                "exit": 0,
                "stdout": [MC_BENIGN_PEEK, r"^T_OBSERVE stage=done$"],
                "stderr": [r"^FAULT_INJECTION boundary=memcached_bipbuffer mode=2 target=2 "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_on_bad_pointer": {
                "env": {**switches(), **MC_FAULT},
                "exit": -REJECT,
                "stdout": [MC_BENIGN_OFFER],
                "stdout_absent": [r"stage=peek_all", r"stage=done"],
                "stderr": [r"^FAULT_INJECTION boundary=memcached_bipbuffer mode=2 target=2 ",
                           r"^INTERSPEC_REJECT boundary=memcached_bipbuffer "
                           r"operation=peek_all reason=untracked$"],
            },
            "benign_all_on": {
                "env": switches(),
                "exit": 0,
                "stdout": [MC_BENIGN_OFFER, MC_BENIGN_PEEK,
                           r"^T_OBSERVE stage=poll returned=1 empty=1$",
                           r"^T_OBSERVE stage=done$"],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_off": {
                "env": switches(sp1="0", sp2="0", sp3="0"),
                "exit": 0,
                "stdout": [MC_BENIGN_OFFER, MC_BENIGN_PEEK,
                           r"^T_OBSERVE stage=poll returned=1 empty=1$",
                           r"^T_OBSERVE stage=done$"],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
        },
    },
}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_case(boundary, name, case, driver, out_dir, timeout):
    case_dir = out_dir / name
    case_dir.mkdir()
    # Only the declared variables reach the driver. Nothing is inherited that
    # could switch a policy or request a fault by accident.
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "INTERSPEC_POLICY_REPORT": "1", **case["env"]}
    (case_dir / "env.json").write_text(json.dumps(env, indent=2, sort_keys=True) + "\n")
    timed_out = False
    try:
        done = subprocess.run([str(driver)], env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout)
        code, out, err = done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired as expired:
        timed_out, code = True, None
        out, err = expired.stdout or b"", expired.stderr or b""
    (case_dir / "stdout.txt").write_bytes(out)
    (case_dir / "stderr.txt").write_bytes(err)
    (case_dir / "exit_code.txt").write_text(f"{code}\n")

    stdout, stderr = out.decode(errors="replace"), err.decode(errors="replace")
    checks = [{"check": "no_timeout", "ok": not timed_out},
              {"check": f"exit=={case['exit']}", "ok": code == case["exit"],
               "observed": code}]
    patterns = [("stdout", stdout, True, case.get("stdout", [])),
                ("stdout", stdout, False, case.get("stdout_absent", [])),
                ("stderr", stderr, True, [policy_line(boundary, case["env"])]
                 + case.get("stderr", [])),
                ("stderr", stderr, False, case.get("stderr_absent", []))]
    for stream, text, wanted, group in patterns:
        for pattern in group:
            found = re.search(pattern, text, re.M) is not None
            checks.append({"check": f"{stream} {'has' if wanted else 'lacks'} /{pattern}/",
                           "ok": found == wanted})
    return {"case": name, "exit": code, "timed_out": timed_out,
            "passed": all(check["ok"] for check in checks), "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary", required=True, choices=sorted(BOUNDARIES))
    parser.add_argument("--driver", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    spec = BOUNDARIES[args.boundary]
    args.out.mkdir(parents=True)  # fails if it exists: no overwriting evidence
    results = {name: run_case(args.boundary, name, case, args.driver, args.out,
                              args.timeout)
               for name, case in spec["cases"].items()}
    tests = {test: {"cases": names,
                    "passed": all(results[name]["passed"] for name in names)}
             for test, names in spec["tests"].items()}
    summary = {"boundary": args.boundary, "driver": str(args.driver),
               "driver_sha256": sha256(args.driver), "tests": tests,
               "cases": results,
               "passed": all(test["passed"] for test in tests.values())}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    for test, record in tests.items():
        print(f"{'PASS' if record['passed'] else 'FAIL'} {args.boundary} {test}")
        for name in record["cases"]:
            for check in results[name]["checks"]:
                if not check["ok"]:
                    print(f"  {name}: failed {check['check']}"
                          + (f" (observed {check['observed']})"
                             if "observed" in check else ""))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
