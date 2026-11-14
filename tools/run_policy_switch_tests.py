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
    return (rf"^INTERSPEC_POLICY boundary={re.escape(boundary)} sp1={env['INTERSPEC_SP1']} "
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

# zip/libzip: the driver is the test build of zip_app_bench on
# evaluation/parity/zip/test.zip (first byte 'P' = 0x50; first entry "test",
# 5 bytes). Rejections exit with 86.
ZIP_ARGS = ["{document}", "1"]
ZIP_BENIGN = (r"^ZIP_BENCH variant=interspec iterations=1 archive_bytes=412 entries=3 "
              r"checksum=[0-9a-f]{16} last_name=74657374 last_size=5 ")
ZIP_T_UNCHANGED = r"^INTERSPEC_T_OBSERVE boundary=zip_libzip archive_first_byte=0x50$"
ZIP_EMPTY_NAME = ["{sibling:filename_empty.zip}", "1"]

# magick/libpng: the driver is the test build of png_app_bench on
# evaluation/parity/png/basn6a08.png (32x32 RGBA; first byte 0x89). One
# iteration decodes it and encodes the pixels again: two registry checks.
# Rejections exit with 86.
PNG_ARGS = ["{document}", "1"]
PNG_BENIGN = (r"^PNG_BENCH variant=interspec iterations=1 input_bytes=184 width=32 "
              r"height=32 rgba_bytes=4096 rgba_fnv=[0-9a-f]{16} png_bytes=\d+ "
              r"png_fnv=[0-9a-f]{16} ")
PNG_T_UNCHANGED = r"^INTERSPEC_T_OBSERVE boundary=magick_libpng png_first_byte=0x89$"

# ffmpeg/libvpx: the driver is the test build of vpx_app_bench on one 64x48
# synthetic frame: one VP8 packet, one decoded frame, four registry checks
# (the packet buffer and three planes). Luma byte 0 of the frame is 0x10.
# Rejections exit with 86.
VPX_ARGS = ["64", "48", "1"]
VPX_BENIGN = (r"^VPX_BENCH variant=interspec frames=1 width=64 height=48 packets=1 "
              r"encoded_bytes=\d+ encoded_fnv=[0-9a-f]{16} decoded_frames=1 "
              r"decoded_fnv=[0-9a-f]{16} ")
VPX_T_UNCHANGED = r"^INTERSPEC_T_OBSERVE boundary=ffmpeg_libvpx luma_first_byte=0x10$"

# nginx/openssl: the driver is the test build of tls_app_bench: a TLS 1.3
# handshake, then one 64-byte request and one 256-byte response. T's receive
# buffer starts out holding "T_STALE_" (hex 545f5354414c455f); byte 0 of the
# response is 'F' = 0x46. In each round T asks for its connection object
# through SSL_get_ex_data and counts the request on it. T's server
# configuration has limit=1000; the other connection has no requests.
TLS_ARGS = ["64", "256", "1"]
TLS_RESULT = (r"request_bytes=64 response_bytes=256 version=TLSv1\.3 cipher=\S+ "
              r"server_received_fnv=[0-9a-f]{16} client_received_fnv=[0-9a-f]{16} ")
TLS_BENIGN = r"^TLS_BENCH variant=interspec rounds=1 " + TLS_RESULT + r"connection_requests=1 "
TLS_T_UNCHANGED = (r"^INTERSPEC_T_OBSERVE boundary=nginx_openssl response_first_byte=0x46 "
                   r"conf_limit=1000 other_requests=0$")


def tls_ex_data_cases(variant, checks_on):
    """The ex_data cases of I6 for one build: legitimate, and three altered values."""
    bench = rf"^TLS_BENCH variant={variant} rounds=1 " + TLS_RESULT
    fault = lambda mode: {**switches(), "INTERSPEC_TEST_FAULT": mode}
    rejected = lambda mode, reason: {
        "env": fault(mode), "args": TLS_ARGS, "exit": 86,
        "stdout_absent": [r"TLS_BENCH"],
        "stderr": [rf"^FAULT_INJECTION boundary=nginx_openssl mode={mode} ",
                   rf"^INTERSPEC_REJECT boundary=nginx_openssl operation=ex_data "
                   rf"reason={reason}$"]}
    cases = {
        "ex_data_legitimate": {
            "env": switches(), "args": TLS_ARGS, "exit": 0,
            "stdout": [bench + r"connection_requests=1 "],
            "stderr": [TLS_T_UNCHANGED],
            "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION"]},
        # A value T never issued: RLBox's handle table refuses it in every build.
        "ex_data_never_issued": rejected("1", "unknown_handle"),
        # The handle of another connection: accepted in every build. The
        # request is counted on the wrong connection. SP3 cannot tell two
        # live objects of the same type apart.
        "ex_data_other_connection": {
            "env": fault("3"), "args": TLS_ARGS, "exit": 0,
            "stdout": [bench + r"connection_requests=0 "],
            "stderr": [r"^FAULT_INJECTION boundary=nginx_openssl mode=3 ",
                       r"^INTERSPEC_T_OBSERVE boundary=nginx_openssl response_first_byte=0x46 "
                       r"conf_limit=1000 other_requests=1$"],
            "stderr_absent": [r"INTERSPEC_REJECT"]},
    }
    if checks_on:
        cases["ex_data_wrong_type"] = rejected("2", "wrong_type")
    else:
        # The handle of T's server configuration: accepted, and T then writes
        # to the configuration as if it were a connection (limit 1000 -> 1001).
        cases["ex_data_wrong_type"] = {
            "env": fault("2"), "args": TLS_ARGS, "exit": 0,
            "stdout": [bench + r"connection_requests=0 "],
            "stderr": [r"^FAULT_INJECTION boundary=nginx_openssl mode=2 ",
                       r"^INTERSPEC_T_OBSERVE boundary=nginx_openssl response_first_byte=0x46 "
                       r"conf_limit=1001 other_requests=0$"],
            "stderr_absent": [r"INTERSPEC_REJECT"]}
    return cases


# memcached/hash: the driver is the test build of hash_app_bench hashing one
# key from a key space of one: "k0", first byte 0x6b. The call returns a
# number: there is no SP1 field and no SP3 field at this boundary.
HASH_ARGS = ["1", "1"]
HASH_BENIGN = r"^HASH_BENCH variant=interspec ops=1 keyspace=1 sink=[0-9a-f]{16} checks=0 "
HASH_T_UNCHANGED = r"^INTERSPEC_T_OBSERVE boundary=memcached_hash key_first_byte=0x6b$"

# memcached/hash with the hash table in U: the driver is the test build of
# assoc_app_bench. The workload cases run 40 cache operations on four keys;
# the first item T inserts has refcount 1 and a key that starts with 'k'
# (0x6b), an expiry time of 0x5ec2e701 and a value that starts with "T_SE".
# The script cases run a fixed order of calls and print which item T was
# handed for key k0.
ASSOC_ARGS = ["4", "40"]
ASSOC_BENCH = r"ops=40 keyspace=4 finds=\d+ hits=\d+ inserts=\d+ deletes=\d+ live=\d+ "
ASSOC_T_UNCHANGED = (r"^INTERSPEC_T_OBSERVE boundary=memcached_hash first_item_refcount=1 "
                     r"first_item_key_byte=0x6b$")


def assoc_handle_cases(variant, registry):
    """What T is handed for k0: legitimate, and three altered handles."""
    script = lambda name, fault=None: {
        **switches(), "INTERSPEC_TEST_SCRIPT": name,
        **({"INTERSPEC_TEST_FAULT": fault} if fault else {})}
    rejected = lambda reason: {
        "args": ASSOC_ARGS, "exit": 86, "stdout_absent": [r"ASSOC_SCRIPT"],
        "stderr": [rf"^INTERSPEC_REJECT boundary=memcached_hash operation=assoc_find "
                   rf"reason={reason}$"]}
    cases = {
        "handle_legitimate": {
            "env": script("find"), "args": ASSOC_ARGS, "exit": 0,
            "stdout": [r"^ASSOC_SCRIPT script=find find_k0=k0$"],
            "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION"]},
        "handle_after_delete_legitimate": {
            "env": script("stale"), "args": ASSOC_ARGS, "exit": 0,
            "stdout": [r"^ASSOC_SCRIPT script=stale find_k0=none$"],
            "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION"]},
        # A value T never issued: refused in every build.
        "handle_never_issued": {
            "env": script("find", "1"),
            **rejected("untracked" if registry else "unknown_handle"),
        },
        # The handle of another live item: accepted in every build; T is handed
        # the item of k1 for k0. SP3 cannot tell two live items apart.
        "handle_other_live_item": {
            "env": script("find", "3"), "args": ASSOC_ARGS, "exit": 0,
            "stdout": [r"^ASSOC_SCRIPT script=find find_k0=k1$"],
            "stderr": [r"^FAULT_INJECTION boundary=memcached_hash mode=3 "],
            "stderr_absent": [r"INTERSPEC_REJECT"]},
    }
    # The handle of an item T has freed, after T inserted another item.
    if registry:
        cases["handle_of_freed_item"] = {"env": script("stale", "2"), **rejected("untracked")}
        cases["handle_of_freed_item"]["stderr"] = [
            r"^FAULT_INJECTION boundary=memcached_hash mode=2 "] + \
            cases["handle_of_freed_item"]["stderr"]
    else:
        # T's handle table has reused the slot: T is handed the new item.
        cases["handle_of_freed_item"] = {
            "env": script("stale", "2"), "args": ASSOC_ARGS, "exit": 0,
            "stdout": [r"^ASSOC_SCRIPT script=stale find_k0=k1$"],
            "stderr": [r"^FAULT_INJECTION boundary=memcached_hash mode=2 "],
            "stderr_absent": [r"INTERSPEC_REJECT"]}
    return cases


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
    "zip_libzip": {
        "tests": {
            "sp1": ["sp1_off_u_reads", "sp1_on_u_reads"],
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            "sp3": ["sp3_off_bad_pointer", "sp3_on_bad_pointer"],
            "sp3_other_faults": ["sp3_on_wrong_type", "sp3_on_released",
                                 "sp3_on_unterminated"],
            "benign": ["benign_all_on", "benign_all_off"],
            # Not a pass criterion of the port but a recorded limit: libzip
            # returns a static empty string for an entry without a name, and
            # the registry does not know static data.
            "limit_static_empty_name": ["limit_empty_name_sp3_off",
                                        "limit_empty_name_sp3_on"],
        },
        "cases": {
            # SP1: U reads what it was handed for the three out-parameters.
            "sp1_off_u_reads": {
                "env": {**switches(sp1="0"), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": ZIP_ARGS, "exit": 0,
                "stdout": [ZIP_BENIGN],
                "stderr": [r"\[SP1\] sandbox read out-parameters size_in=0x5ec2e70100000001 "
                           r"name_direct_in=0x5ec2e702 name_stat_in=0x5ec2e703$"],
            },
            "sp1_on_u_reads": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": ZIP_ARGS, "exit": 0,
                "stdout": [ZIP_BENIGN],
                "stderr": [r"\[SP1\] sandbox read out-parameters size_in=0x0 "
                           r"name_direct_in=0x0 name_stat_in=0x0$"],
                "stderr_absent": [r"5ec2e7"],
            },
            # SP2: U overwrites its copy of the archive after opening it.
            "sp2_off_u_writes": {
                "env": {**switches(sp2="0"), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": ZIP_ARGS, "exit": 0,
                "stdout": [ZIP_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated archive byte=0 old=0x50 new=0xaf$",
                           r"^INTERSPEC_T_OBSERVE boundary=zip_libzip archive_first_byte=0xaf$"],
            },
            "sp2_on_u_writes": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": ZIP_ARGS, "exit": 0,
                "stdout": [ZIP_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated archive byte=0 old=0x50 new=0xaf$",
                           ZIP_T_UNCHANGED],
            },
            # SP3: U returns an untracked heap copy of the first name.
            "sp3_off_bad_pointer": {
                "env": switches(sp3="0"),
                "args": ZIP_ARGS + ["2"], "exit": 0,
                "stdout": [ZIP_BENIGN + r"checks=0 "],
                "stderr": [r"^FAULT_INJECTION boundary=zip_libzip mode=2 "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_on_bad_pointer": {
                "env": switches(),
                "args": ZIP_ARGS + ["2"], "exit": 86,
                "stdout_absent": [r"ZIP_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=zip_libzip mode=2 ",
                           r"^INTERSPEC_REJECT boundary=zip_libzip operation=name_direct "
                           r"reason=untracked$"],
            },
            # SP3 on, the other ways in which the returned pointer can be wrong.
            "sp3_on_wrong_type": {
                "env": switches(),
                "args": ZIP_ARGS + ["1"], "exit": 86,
                "stdout_absent": [r"ZIP_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=zip_libzip mode=1 ",
                           r"^INTERSPEC_REJECT boundary=zip_libzip operation=name_direct "
                           r"reason=wrong_type$"],
            },
            "sp3_on_released": {
                "env": switches(),
                "args": ZIP_ARGS + ["3"], "exit": 86,
                "stdout_absent": [r"ZIP_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=zip_libzip mode=3 ",
                           r"^INTERSPEC_REJECT boundary=zip_libzip operation=name_direct "
                           r"reason=untracked$"],
            },
            "sp3_on_unterminated": {
                "env": switches(),
                "args": ZIP_ARGS + ["4"], "exit": 86,
                "stdout_absent": [r"ZIP_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=zip_libzip mode=4 ",
                           r"^INTERSPEC_REJECT boundary=zip_libzip operation=name_direct "
                           r"reason=out_of_bounds$"],
            },
            "benign_all_on": {
                "env": switches(),
                "args": ZIP_ARGS, "exit": 0,
                "stdout": [ZIP_BENIGN + r"checks=2 "],
                "stderr": [ZIP_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_off": {
                "env": switches(sp1="0", sp2="0", sp3="0"),
                "args": ZIP_ARGS, "exit": 0,
                "stdout": [ZIP_BENIGN + r"checks=0 "],
                "stderr": [ZIP_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "limit_empty_name_sp3_off": {
                "env": switches(sp3="0"),
                "args": ZIP_EMPTY_NAME, "exit": 0,
                "stdout": [r"^ZIP_BENCH variant=interspec iterations=1 archive_bytes=98 "
                           r"entries=1 checksum=[0-9a-f]{16} last_name=\(empty\) "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "limit_empty_name_sp3_on": {
                "env": switches(),
                "args": ZIP_EMPTY_NAME, "exit": 86,
                "stdout_absent": [r"ZIP_BENCH"],
                "stderr": [r"^INTERSPEC_REJECT boundary=zip_libzip operation=name_direct "
                           r"reason=untracked$"],
            },
        },
    },
    "magick_libpng": {
        "tests": {
            "sp1": ["sp1_off_u_reads", "sp1_on_u_reads"],
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            "sp3": ["sp3_off_bad_pointer", "sp3_on_bad_pointer"],
            "sp3_other_faults": ["sp3_on_wrong_type", "sp3_on_released",
                                 "sp3_on_too_small"],
            "benign": ["benign_all_on", "benign_all_off"],
        },
        "cases": {
            # SP1: U reads what it was handed for the out-parameters of decode.
            "sp1_off_u_reads": {
                "env": {**switches(sp1="0"), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": PNG_ARGS, "exit": 0,
                "stdout": [PNG_BENIGN],
                "stderr": [r"\[SP1\] sandbox read out-parameters w_in=0x5ec2e701 "
                           r"h_in=0x5ec2e702 rgba_in=0x[0-9a-f]*[1-9a-f][0-9a-f]* "
                           r"size_in=0x5ec2e703$"],
            },
            "sp1_on_u_reads": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": PNG_ARGS, "exit": 0,
                "stdout": [PNG_BENIGN],
                "stderr": [r"\[SP1\] sandbox read out-parameters w_in=0x0 h_in=0x0 "
                           r"rgba_in=0x0 size_in=0x0$"],
                "stderr_absent": [r"5ec2e7"],
            },
            # SP2: U overwrites its copy of the PNG bytes after decoding.
            "sp2_off_u_writes": {
                "env": {**switches(sp2="0"), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": PNG_ARGS, "exit": 0,
                "stdout": [PNG_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated png byte=0 old=0x89 new=0x76$",
                           r"^INTERSPEC_T_OBSERVE boundary=magick_libpng png_first_byte=0x76$"],
            },
            "sp2_on_u_writes": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": PNG_ARGS, "exit": 0,
                "stdout": [PNG_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated png byte=0 old=0x89 new=0x76$",
                           PNG_T_UNCHANGED],
            },
            # SP3: U returns an untracked heap copy of the decoded pixels.
            "sp3_off_bad_pointer": {
                "env": switches(sp3="0"),
                "args": PNG_ARGS + ["2"], "exit": 0,
                "stdout": [PNG_BENIGN + r"checks=0 "],
                "stderr": [r"^FAULT_INJECTION boundary=magick_libpng mode=2 "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_on_bad_pointer": {
                "env": switches(),
                "args": PNG_ARGS + ["2"], "exit": 86,
                "stdout_absent": [r"PNG_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=magick_libpng mode=2 ",
                           r"^INTERSPEC_REJECT boundary=magick_libpng operation=decoded_pixels "
                           r"reason=untracked$"],
            },
            # SP3 on, the other ways in which the returned pointer can be wrong.
            "sp3_on_wrong_type": {
                "env": switches(),
                "args": PNG_ARGS + ["1"], "exit": 86,
                "stdout_absent": [r"PNG_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=magick_libpng mode=1 ",
                           r"^INTERSPEC_REJECT boundary=magick_libpng operation=decoded_pixels "
                           r"reason=wrong_type$"],
            },
            "sp3_on_released": {
                "env": switches(),
                "args": PNG_ARGS + ["3"], "exit": 86,
                "stdout_absent": [r"PNG_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=magick_libpng mode=3 ",
                           r"^INTERSPEC_REJECT boundary=magick_libpng operation=decoded_pixels "
                           r"reason=untracked$"],
            },
            "sp3_on_too_small": {
                "env": switches(),
                "args": PNG_ARGS + ["4"], "exit": 86,
                "stdout_absent": [r"PNG_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=magick_libpng mode=4 ",
                           r"^INTERSPEC_REJECT boundary=magick_libpng operation=decoded_pixels "
                           r"reason=out_of_bounds$"],
            },
            "benign_all_on": {
                "env": switches(),
                "args": PNG_ARGS, "exit": 0,
                "stdout": [PNG_BENIGN + r"checks=2 "],
                "stderr": [PNG_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_off": {
                "env": switches(sp1="0", sp2="0", sp3="0"),
                "args": PNG_ARGS, "exit": 0,
                "stdout": [PNG_BENIGN + r"checks=0 "],
                "stderr": [PNG_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
        },
    },
    "ffmpeg_libvpx": {
        "tests": {
            "sp1": ["sp1_off_u_reads", "sp1_on_u_reads"],
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            "sp3": ["sp3_off_bad_pointer", "sp3_on_bad_pointer"],
            "sp3_other_faults": ["sp3_on_wrong_type", "sp3_on_released",
                                 "sp3_on_too_small"],
            "benign": ["benign_all_on", "benign_all_off"],
        },
        "cases": {
            # SP1: U reads the image fields that the encoder does not use.
            "sp1_off_u_reads": {
                "env": {**switches(sp1="0"), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": VPX_ARGS, "exit": 0,
                "stdout": [VPX_BENIGN],
                "stderr": [r"\[SP1\] sandbox read image fields user_priv=0x5ec2e701 "
                           r"img_data=0x[0-9a-f]*[1-9a-f][0-9a-f]* fb_priv=0x5ec2e703 "
                           r"img_data_owner=1$"],
            },
            "sp1_on_u_reads": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": VPX_ARGS, "exit": 0,
                "stdout": [VPX_BENIGN],
                "stderr": [r"\[SP1\] sandbox read image fields user_priv=0x0 img_data=0x0 "
                           r"fb_priv=0x0 img_data_owner=0$"],
                "stderr_absent": [r"5ec2e7"],
            },
            # SP2: U overwrites its copy of the luma plane after encoding.
            "sp2_off_u_writes": {
                "env": {**switches(sp2="0"), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": VPX_ARGS, "exit": 0,
                "stdout": [VPX_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated luma byte=0 old=0x10 new=0xef$",
                           r"^INTERSPEC_T_OBSERVE boundary=ffmpeg_libvpx luma_first_byte=0xef$"],
            },
            "sp2_on_u_writes": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": VPX_ARGS, "exit": 0,
                "stdout": [VPX_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated luma byte=0 old=0x10 new=0xef$",
                           VPX_T_UNCHANGED],
            },
            # SP3: U returns an untracked heap copy of the luma plane.
            "sp3_off_bad_pointer": {
                "env": switches(sp3="0"),
                "args": VPX_ARGS + ["2"], "exit": 0,
                "stdout": [VPX_BENIGN + r"checks=0 "],
                "stderr": [r"^FAULT_INJECTION boundary=ffmpeg_libvpx mode=2 "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_on_bad_pointer": {
                "env": switches(),
                "args": VPX_ARGS + ["2"], "exit": 86,
                "stdout_absent": [r"VPX_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=ffmpeg_libvpx mode=2 ",
                           r"^INTERSPEC_REJECT boundary=ffmpeg_libvpx operation=frame_plane "
                           r"reason=untracked$"],
            },
            # SP3 on, the other ways in which the returned pointer can be wrong.
            "sp3_on_wrong_type": {
                "env": switches(),
                "args": VPX_ARGS + ["1"], "exit": 86,
                "stdout_absent": [r"VPX_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=ffmpeg_libvpx mode=1 ",
                           r"^INTERSPEC_REJECT boundary=ffmpeg_libvpx operation=frame_plane "
                           r"reason=wrong_type$"],
            },
            "sp3_on_released": {
                "env": switches(),
                "args": VPX_ARGS + ["3"], "exit": 86,
                "stdout_absent": [r"VPX_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=ffmpeg_libvpx mode=3 ",
                           r"^INTERSPEC_REJECT boundary=ffmpeg_libvpx operation=frame_plane "
                           r"reason=untracked$"],
            },
            "sp3_on_too_small": {
                "env": switches(),
                "args": VPX_ARGS + ["4"], "exit": 86,
                "stdout_absent": [r"VPX_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=ffmpeg_libvpx mode=4 ",
                           r"^INTERSPEC_REJECT boundary=ffmpeg_libvpx operation=frame_plane "
                           r"reason=out_of_bounds$"],
            },
            "benign_all_on": {
                "env": switches(),
                "args": VPX_ARGS, "exit": 0,
                "stdout": [VPX_BENIGN + r"checks=4 "],
                "stderr": [VPX_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_off": {
                "env": switches(sp1="0", sp2="0", sp3="0"),
                "args": VPX_ARGS, "exit": 0,
                "stdout": [VPX_BENIGN + r"checks=0 "],
                "stderr": [VPX_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
        },
    },
    "nginx_openssl": {
        "tests": {
            "sp1": ["sp1_off_u_reads", "sp1_on_u_reads"],
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            # SP3: U returns the handle of T's server configuration where T
            # expects its connection object.
            "sp3": ["sp3_off_bad_pointer", "sp3_on_bad_pointer"],
            # I6: the legitimate value and three altered ones, all policies on.
            "ex_data": ["ex_data_legitimate", "ex_data_never_issued", "ex_data_wrong_type",
                        "ex_data_other_connection"],
            "benign": ["benign_all_on", "benign_all_off"],
        },
        "cases": {
            # SP1: U reads the output buffer it was handed before writing to it.
            "sp1_off_u_reads": {
                "env": {**switches(sp1="0"), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": TLS_ARGS, "exit": 0,
                "stdout": [TLS_BENIGN],
                "stderr": [r"\[SP1\] sandbox read output buffer before writing "
                           r"first8=545f5354414c455f$"],
            },
            "sp1_on_u_reads": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": TLS_ARGS, "exit": 0,
                "stdout": [TLS_BENIGN],
                "stderr": [r"\[SP1\] sandbox read output buffer before writing "
                           r"first8=[0-9a-f]{16}$"],
                "stderr_absent": [r"545f5354414c455f"],
            },
            # SP2: U overwrites its copy of the plaintext after sending it.
            "sp2_off_u_writes": {
                "env": {**switches(sp2="0"), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": TLS_ARGS, "exit": 0,
                "stdout": [TLS_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated plaintext byte=0 old=0x46 new=0xb9$",
                           r"^INTERSPEC_T_OBSERVE boundary=nginx_openssl "
                           r"response_first_byte=0xb9 conf_limit=1000 other_requests=0$"],
            },
            "sp2_on_u_writes": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": TLS_ARGS, "exit": 0,
                "stdout": [TLS_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated plaintext byte=0 old=0x46 new=0xb9$",
                           TLS_T_UNCHANGED],
            },
            "sp3_off_bad_pointer": {
                "env": {**switches(sp3="0"), "INTERSPEC_TEST_FAULT": "2"},
                "args": TLS_ARGS, "exit": 0,
                "stdout": [r"^TLS_BENCH variant=interspec rounds=1 " + TLS_RESULT +
                           r"connection_requests=0 checks=0 "],
                "stderr": [r"^FAULT_INJECTION boundary=nginx_openssl mode=2 ",
                           r"^INTERSPEC_T_OBSERVE boundary=nginx_openssl "
                           r"response_first_byte=0x46 conf_limit=1001 other_requests=0$"],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_on_bad_pointer": {
                "env": {**switches(), "INTERSPEC_TEST_FAULT": "2"},
                "args": TLS_ARGS, "exit": 86,
                "stdout_absent": [r"TLS_BENCH"],
                "stderr": [r"^FAULT_INJECTION boundary=nginx_openssl mode=2 ",
                           r"^INTERSPEC_REJECT boundary=nginx_openssl operation=ex_data "
                           r"reason=wrong_type$"],
            },
            **tls_ex_data_cases("interspec", True),
            "benign_all_on": {
                "env": switches(),
                "args": TLS_ARGS, "exit": 0,
                "stdout": [TLS_BENIGN + r"checks=1 "],
                "stderr": [TLS_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_off": {
                "env": switches(sp1="0", sp2="0", sp3="0"),
                "args": TLS_ARGS, "exit": 0,
                "stdout": [TLS_BENIGN + r"checks=0 "],
                "stderr": [TLS_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
        },
    },
    # I6: the same ex_data cases on the build without any InterSpec check.
    "nginx_openssl_rlbox_only": {
        "reported_as": "nginx_openssl+sp3_fixed_at_compile_time",
        "tests": {
            "ex_data": ["ex_data_legitimate", "ex_data_never_issued", "ex_data_wrong_type",
                        "ex_data_other_connection"],
        },
        "cases": tls_ex_data_cases("rlbox-only", False),
    },
    "memcached_hash": {
        "tests": {
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            # Recorded, not switch tests: the call hands U nothing it does not
            # read and U returns no pointer, so these switches have nothing to
            # act on.
            "sp1_no_field": ["benign_all_on", "sp1_off_same_behavior"],
            "sp3_no_field": ["benign_all_on", "sp3_off_same_behavior"],
            "benign": ["benign_all_on", "benign_all_off"],
        },
        "cases": {
            # SP2: U overwrites its copy of the key after hashing it.
            "sp2_off_u_writes": {
                "env": {**switches(sp2="0"), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": HASH_ARGS, "exit": 0,
                "stdout": [HASH_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated key byte=0 old=0x6b new=0x94$",
                           r"^INTERSPEC_T_OBSERVE boundary=memcached_hash key_first_byte=0x94$"],
            },
            "sp2_on_u_writes": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": HASH_ARGS, "exit": 0,
                "stdout": [HASH_BENIGN],
                "stderr": [r"\[SP2\] sandbox mutated key byte=0 old=0x6b new=0x94$",
                           HASH_T_UNCHANGED],
            },
            "sp1_off_same_behavior": {
                "env": switches(sp1="0"),
                "args": HASH_ARGS, "exit": 0,
                "stdout": [HASH_BENIGN],
                "stderr": [HASH_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "sp3_off_same_behavior": {
                "env": switches(sp3="0"),
                "args": HASH_ARGS, "exit": 0,
                "stdout": [HASH_BENIGN],
                "stderr": [HASH_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_on": {
                "env": switches(),
                "args": HASH_ARGS, "exit": 0,
                "stdout": [HASH_BENIGN],
                "stderr": [HASH_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_off": {
                "env": switches(sp1="0", sp2="0", sp3="0"),
                "args": HASH_ARGS, "exit": 0,
                "stdout": [HASH_BENIGN],
                "stderr": [HASH_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
        },
    },
    "memcached_assoc": {
        "reported_as": "memcached_hash",
        "tests": {
            "sp1": ["sp1_off_u_reads", "sp1_on_u_reads"],
            "sp2": ["sp2_off_u_writes", "sp2_on_u_writes"],
            # SP3: U returns the handle of an item that T has freed.
            "sp3": ["sp3_off_bad_pointer", "sp3_on_bad_pointer"],
            "handles": ["handle_legitimate", "handle_after_delete_legitimate",
                        "handle_never_issued", "handle_of_freed_item",
                        "handle_other_live_item"],
            "benign": ["benign_all_on", "benign_all_off"],
        },
        "cases": {
            # SP1: U reads the item fields and value bytes that the hash table
            # does not need.
            "sp1_off_u_reads": {
                "env": {**switches(sp1="0"), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": ASSOC_ARGS, "exit": 0,
                "stdout": [r"^ASSOC_BENCH variant=interspec " + ASSOC_BENCH],
                "stderr": [r"\[SP1\] sandbox read item exptime=0x5ec2e701 nbytes=[1-9]\d* "
                           r"value_bytes_received=[1-9]\d* value_first4=545f5345$"],
            },
            "sp1_on_u_reads": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "1"},
                "args": ASSOC_ARGS, "exit": 0,
                "stdout": [r"^ASSOC_BENCH variant=interspec " + ASSOC_BENCH],
                "stderr": [r"\[SP1\] sandbox read item exptime=0x0 nbytes=0 "
                           r"value_bytes_received=0 value_first4=00000000$"],
                "stderr_absent": [r"5ec2e7", r"545f5345"],
            },
            # SP2: U overwrites the reference count and the key in its copy of
            # the item. Without SP2 T's item is changed, and its cache with it.
            "sp2_off_u_writes": {
                "env": {**switches(sp2="0"), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": ASSOC_ARGS, "exit": 0,
                "stderr": [r"\[SP2\] sandbox mutated item refcount=0xffff key_byte0=0x94$",
                           r"^INTERSPEC_T_OBSERVE boundary=memcached_hash "
                           r"first_item_refcount=65535 first_item_key_byte=0x94$"],
            },
            "sp2_on_u_writes": {
                "env": {**switches(), "INTERSPEC_TEST_POC_FLAGS": "2"},
                "args": ASSOC_ARGS, "exit": 0,
                "stdout": [r"^ASSOC_BENCH variant=interspec " + ASSOC_BENCH],
                "stderr": [r"\[SP2\] sandbox mutated item refcount=0xffff key_byte0=0x94$",
                           ASSOC_T_UNCHANGED],
            },
            "sp3_off_bad_pointer": {
                "env": {**switches(sp3="0"), "INTERSPEC_TEST_SCRIPT": "stale",
                        "INTERSPEC_TEST_FAULT": "2"},
                "args": ASSOC_ARGS, "exit": 0,
                "stdout": [r"^ASSOC_SCRIPT script=stale find_k0=k1$"],
                "stderr": [r"^FAULT_INJECTION boundary=memcached_hash mode=2 "],
                "stderr_absent": [r"INTERSPEC_REJECT"],
            },
            "sp3_on_bad_pointer": {
                "env": {**switches(), "INTERSPEC_TEST_SCRIPT": "stale",
                        "INTERSPEC_TEST_FAULT": "2"},
                "args": ASSOC_ARGS, "exit": 86,
                "stdout_absent": [r"ASSOC_SCRIPT"],
                "stderr": [r"^FAULT_INJECTION boundary=memcached_hash mode=2 ",
                           r"^INTERSPEC_REJECT boundary=memcached_hash operation=assoc_find "
                           r"reason=untracked$"],
            },
            **assoc_handle_cases("interspec", True),
            "benign_all_on": {
                "env": switches(),
                "args": ASSOC_ARGS, "exit": 0,
                "stdout": [r"^ASSOC_BENCH variant=interspec " + ASSOC_BENCH +
                           r".* checks=[1-9]\d* "],
                "stderr": [ASSOC_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
            "benign_all_off": {
                "env": switches(sp1="0", sp2="0", sp3="0"),
                "args": ASSOC_ARGS, "exit": 0,
                "stdout": [r"^ASSOC_BENCH variant=interspec " + ASSOC_BENCH + r".* checks=0 "],
                "stderr": [ASSOC_T_UNCHANGED],
                "stderr_absent": [r"INTERSPEC_REJECT", r"FAULT_INJECTION", r"PoC"],
            },
        },
    },
    # The same handle cases on the build without any InterSpec check.
    "memcached_assoc_rlbox_only": {
        "reported_as": "memcached_hash+sp3_fixed_at_compile_time",
        "tests": {
            "handles": ["handle_legitimate", "handle_after_delete_legitimate",
                        "handle_never_issued", "handle_of_freed_item",
                        "handle_other_live_item"],
        },
        "cases": assoc_handle_cases("rlbox-only", False),
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
        def expand(arg):  # {document}, or {sibling:NAME} next to the document
            if arg == "{document}":
                return str(document)
            if arg.startswith("{sibling:") and arg.endswith("}"):
                return str(document.parent / arg[len("{sibling:"):-1])
            return arg
        command = [str(driver)] + [expand(arg) for arg in case.get("args", [])]
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
    reported = BOUNDARIES[boundary].get("reported_as", boundary)
    patterns = [("stdout", stdout, True, case.get("stdout", [])),
                ("stdout", stdout, False, case.get("stdout_absent", [])),
                ("stderr", stderr, True, [policy_line(reported, case["env"])]
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
