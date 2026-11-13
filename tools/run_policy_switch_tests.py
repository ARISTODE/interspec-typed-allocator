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
    sp3 = {"0": "off", "1": "full"}[env["INTERSPEC_SP3"]]
    return (rf"^INTERSPEC_POLICY boundary={boundary} sp1={env['INTERSPEC_SP1']} "
            rf"sp2={env['INTERSPEC_SP2']} sp3={sp3}$")


REJECT = signal.SIGABRT

# memcached/bipbuffer driver: the 16-byte record "T_RECORD_0123456" in hex.
MC_RECORD = "545f5245434f52445f30313233343536"
MC_BENIGN_OFFER = r"^T_OBSERVE stage=offer written=16 record=" + MC_RECORD + "$"
MC_BENIGN_PEEK = r"^T_OBSERVE stage=peek_all size=16 data=" + MC_RECORD + "$"
MC_FAULT = {"INTERSPEC_TEST_FAULT": "2", "INTERSPEC_TEST_TARGET": "2",
            "INTERSPEC_TEST_ROLE": "1"}

# nginx/libpcre driver: subject "/items/123/alpha" in hex, and its captures.
NGX_SUBJECT = "2f6974656d732f3132332f616c706861"
NGX_BENIGN = (r"^T_OBSERVE stage=exec rc=3 subject=" + NGX_SUBJECT +
              r" captures=0-16,7-10,11-16$")
NGX_FAULT = {"INTERSPEC_NGINX_FAULT_PATH": "2", "INTERSPEC_NGINX_FAULT_KIND": "2"}

# yaml/libyaml: the driver is the fault build of yaml_app_bench, run on
# evaluation/parity/yaml/block_flow.yaml (first byte 'k' = 0x6b). The bench
# rejects with exit status 86 instead of aborting.
YAML_ARGS = ["extended_sp3", "{document}", "1"]
YAML_BENIGN = (r"^YAML_BENCH mode=extended_sp3 iterations=1 input_bytes=\d+ "
               r"events=23 scalars=11 scalar_bytes=\d+ hash=[0-9a-f]{16} ")
YAML_REJECT_EXIT = 86

# ucl/libucl: the driver is the test build of ucl_app_bench on
# evaluation/parity/ucl/nested.conf (first byte 's' = 0x73), looking up
# server.name ("alpha") and logging.level ("debug"). Rejections exit with 86.
UCL_ARGS = ["{document}", "server.name", "logging.level", "1"]
UCL_BENIGN = (r"^UCL_BENCH variant=interspec iterations=1 input_bytes=\d+ "
              r"val1=616c706861 val2=6465627567 emitted_bytes=\d+ emitted_fnv=[0-9a-f]{16} ")
UCL_T_UNCHANGED = r"^INTERSPEC_T_OBSERVE boundary=ucl_libucl input_first_byte=0x73 key1_first_byte=0x73$"

# Each case: switch settings, test-only U behavior, and what must be observed.
# "exit" is a return code; a negative value is the signal that ended the process.
BOUNDARIES = {
    "rsync_popt": {
        "tests": {
            "sp1": ["sp1_off_u_reads", "sp1_on_u_reads"],
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            "sp3": ["sp3_off_bad_pointer", "sp3_on_bad_pointer"],
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
            "sp3": ["sp3_off_bad_pointer", "sp3_on_bad_pointer"],
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
    "nginx_pcre": {
        "tests": {
            "sp1": ["sp1_off_u_reads", "sp1_on_u_reads"],
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            "sp3": ["sp3_off_bad_pointer", "sp3_on_bad_pointer"],
            "benign": ["benign_all_on", "benign_all_off"],
        },
        "cases": {
            # SP1: U reads the output vector of pcre_exec on entry. T filled it
            # with 0x5ec2e7 before the call.
            "sp1_off_u_reads": {
                "env": {**switches(sp1="0"), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "exit": 0,
                "stdout": [NGX_BENIGN, r"^T_OBSERVE stage=done$"],
                "stderr": [r"\[SP1\] sandbox read exec ovector\[0\]=0x5ec2e7$"],
            },
            "sp1_on_u_reads": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "exit": 0,
                "stdout": [NGX_BENIGN, r"^T_OBSERVE stage=done$"],
                "stderr": [r"\[SP1\] sandbox read exec ovector\[0\]=0xffffffff$"],
                "stderr_absent": [r"5ec2e7"],
            },
            # SP2: U overwrites its copy of the subject passed to pcre_exec.
            "sp2_off_u_writes": {
                "env": {**switches(sp2="0"), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "exit": 0,
                "stdout": [r"^T_OBSERVE stage=exec rc=3 subject=d0" + NGX_SUBJECT[2:] +
                           r" captures=0-16,7-10,11-16$", r"^T_OBSERVE stage=done$"],
                "stderr": [r"\[SP2\] sandbox mutated subject byte=0 old=0x2f new=0xd0$"],
            },
            "sp2_on_u_writes": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "exit": 0,
                "stdout": [NGX_BENIGN, r"^T_OBSERVE stage=done$"],
                "stderr": [r"\[SP2\] sandbox mutated subject byte=0 old=0x2f new=0xd0$"],
            },
            # SP3: U returns an untracked heap copy of the capture offsets.
            "sp3_off_bad_pointer": {
                "env": {**switches(sp3="0"), **NGX_FAULT},
                "exit": 0,
                "stdout": [NGX_BENIGN, r"^T_OBSERVE stage=done$"],
                "stderr": [r"^FAULT_INJECTION boundary=nginx_pcre path=2 kind=2 "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_on_bad_pointer": {
                "env": {**switches(), **NGX_FAULT},
                "exit": -REJECT,
                "stdout": [r"^T_OBSERVE stage=compile result=ok$"],
                "stdout_absent": [r"stage=exec", r"stage=done"],
                "stderr": [r"^FAULT_INJECTION boundary=nginx_pcre path=2 kind=2 ",
                           r"^INTERSPEC_REJECT boundary=nginx_pcre "
                           r"operation=capture_offsets reason=untracked$"],
            },
            "benign_all_on": {
                "env": switches(),
                "exit": 0,
                "stdout": [r"^T_OBSERVE stage=compile result=ok$", NGX_BENIGN,
                           r"^T_OBSERVE stage=done$"],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_off": {
                "env": switches(sp1="0", sp2="0", sp3="0"),
                "exit": 0,
                "stdout": [r"^T_OBSERVE stage=compile result=ok$", NGX_BENIGN,
                           r"^T_OBSERVE stage=done$"],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
        },
    },
    "yaml_libyaml": {
        # No SP1 test: T sends U only the document, which U has to read, so
        # there is no field to withhold (EVAL_TRACKER.md, I3).
        "tests": {
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            "sp3": ["sp3_off_bad_pointer", "sp3_on_bad_pointer"],
            "benign": ["benign_all_on", "benign_all_off"],
        },
        "cases": {
            # SP2: U overwrites its copy of the document after parsing.
            "sp2_off_u_writes": {
                "env": {**switches(sp2="0"), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": YAML_ARGS, "exit": 0,
                "stdout": [YAML_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated document byte=0 old=0x6b new=0x94$",
                           r"^INTERSPEC_T_OBSERVE boundary=yaml_libyaml input_first_byte=0x94$"],
            },
            "sp2_on_u_writes": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": YAML_ARGS, "exit": 0,
                "stdout": [YAML_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated document byte=0 old=0x6b new=0x94$",
                           r"^INTERSPEC_T_OBSERVE boundary=yaml_libyaml input_first_byte=0x6b$"],
            },
            # SP3: U returns an untracked heap copy of the first scalar.
            "sp3_off_bad_pointer": {
                "env": switches(sp3="0"),
                "args": YAML_ARGS + ["2"], "exit": 0,
                "stdout": [YAML_BENIGN],
                "stderr": [r"^FAULT_INJECTION boundary=yaml_libyaml mode=2 "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_on_bad_pointer": {
                "env": switches(),
                "args": YAML_ARGS + ["2"], "exit": YAML_REJECT_EXIT,
                "stdout_absent": [r"YAML_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=yaml_libyaml mode=2 ",
                           r"^INTERSPEC_REJECT boundary=yaml_libyaml reason=untracked$"],
            },
            "benign_all_on": {
                "env": switches(),
                "args": YAML_ARGS, "exit": 0,
                "stdout": [YAML_BENIGN + r"checks=11 "],
                "stderr": [r"^INTERSPEC_T_OBSERVE boundary=yaml_libyaml input_first_byte=0x6b$"],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_off": {
                "env": switches(sp1="0", sp2="0", sp3="0"),
                "args": YAML_ARGS, "exit": 0,
                "stdout": [YAML_BENIGN + r"checks=0 "],
                "stderr": [r"^INTERSPEC_T_OBSERVE boundary=yaml_libyaml input_first_byte=0x6b$"],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
        },
    },
    "ucl_libucl": {
        "tests": {
            "sp1": ["sp1_off_u_reads", "sp1_on_u_reads"],
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            "sp3": ["sp3_off_bad_pointer", "sp3_on_bad_pointer"],
            "benign": ["benign_all_on", "benign_all_off"],
        },
        "cases": {
            # SP1: U reads what it was handed for the three out-parameters.
            "sp1_off_u_reads": {
                "env": {**switches(sp1="0"), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": UCL_ARGS, "exit": 0,
                "stdout": [UCL_BENIGN],
                "stderr": [r"\[SP1\] sandbox read out-parameters val1_in=0x5ec2e701 "
                           r"val2_in=0x5ec2e702 emitted_in=0x5ec2e703$"],
            },
            "sp1_on_u_reads": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": UCL_ARGS, "exit": 0,
                "stdout": [UCL_BENIGN],
                "stderr": [r"\[SP1\] sandbox read out-parameters val1_in=0x0 "
                           r"val2_in=0x0 emitted_in=0x0$"],
                "stderr_absent": [r"5ec2e7"],
            },
            # SP2: U overwrites its copy of the document after parsing.
            "sp2_off_u_writes": {
                "env": {**switches(sp2="0"), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": UCL_ARGS, "exit": 0,
                "stdout": [UCL_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated document byte=0 old=0x73 new=0x8c$",
                           r"^INTERSPEC_T_OBSERVE boundary=ucl_libucl input_first_byte=0x8c "],
            },
            "sp2_on_u_writes": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": UCL_ARGS, "exit": 0,
                "stdout": [UCL_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated document byte=0 old=0x73 new=0x8c$",
                           UCL_T_UNCHANGED],
            },
            # SP3: U returns an untracked heap copy of the first string.
            "sp3_off_bad_pointer": {
                "env": switches(sp3="0"),
                "args": UCL_ARGS + ["2"], "exit": 0,
                "stdout": [UCL_BENIGN + r"checks=0 "],
                "stderr": [r"^FAULT_INJECTION boundary=ucl_libucl mode=2 "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_on_bad_pointer": {
                "env": switches(),
                "args": UCL_ARGS + ["2"], "exit": 86,
                "stdout_absent": [r"UCL_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=ucl_libucl mode=2 ",
                           r"^INTERSPEC_REJECT boundary=ucl_libucl operation=string_value "
                           r"reason=untracked$"],
            },
            "benign_all_on": {
                "env": switches(),
                "args": UCL_ARGS, "exit": 0,
                "stdout": [UCL_BENIGN + r"checks=3 "],
                "stderr": [UCL_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_off": {
                "env": switches(sp1="0", sp2="0", sp3="0"),
                "args": UCL_ARGS, "exit": 0,
                "stdout": [UCL_BENIGN + r"checks=0 "],
                "stderr": [UCL_T_UNCHANGED],
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


def run_case(boundary, name, case, driver, out_dir, timeout, document=None):
    case_dir = out_dir / name
    case_dir.mkdir()
    # Only the declared variables reach the driver. Nothing is inherited that
    # could switch a policy or request a fault by accident.
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "INTERSPEC_POLICY_REPORT": "1", **case["env"]}
    (case_dir / "env.json").write_text(json.dumps(env, indent=2, sort_keys=True) + "\n")
    timed_out = False
    try:
        command = [str(driver)] + [str(document) if arg == "{document}" else arg
                                   for arg in case.get("args", [])]
        (case_dir / "command.json").write_text(json.dumps(command) + "\n")
        done = subprocess.run(command, env=env, stdout=subprocess.PIPE,
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
    parser.add_argument("--document", type=Path,
                        help="input file for drivers that take one (yaml_libyaml)")
    args = parser.parse_args()

    spec = BOUNDARIES[args.boundary]
    args.out.mkdir(parents=True)  # fails if it exists: no overwriting evidence
    results = {name: run_case(args.boundary, name, case, args.driver, args.out,
                              args.timeout, args.document)
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
