#!/usr/bin/env python3
"""Build and validate a current-source client for a separately versioned profile.

This only runs valid-response, count-only loopback fixtures, not an application
experiment. Every output directory is create-once, including failed builds.
"""
from argparse import Namespace
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

SOURCES = ("evaluation/memcached_client.cpp", "evaluation/memcached_workload.h",
           "evaluation/memcached_measurement.h", "tests/memcached_buffered_protocol.py")
SUCCESS = "10 buffered stream functional cases passed; no performance evidence\n"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare_inputs(args, root):
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    # Generated untracked results do not change source identity. Tracked edits do.
    subprocess.run(["git", "-C", str(root), "diff", "--exit-code", "HEAD", "--"], check=True,
                   stdout=subprocess.DEVNULL)
    source_hashes = {relative: sha(root / relative) for relative in SOURCES}
    for relative in SOURCES:
        tracked = subprocess.check_output(["git", "-C", str(root), "show", revision + ":" + relative])
        if hashlib.sha256(tracked).hexdigest() != source_hashes[relative]:
            raise ValueError("client source differs from selected commit: " + relative)
    build = args.client_build_directory.resolve()
    build.mkdir(parents=True, exist_ok=False)
    compiler = Path(shutil.which("g++") or "g++").resolve()
    client = build / "memcached-client"
    command = [str(compiler), "-std=c++17", "-O2", "-pthread",
               str(root / SOURCES[0]), "-o", str(client)]
    version = subprocess.check_output([str(compiler), "--version"])
    (build / "compiler-version.txt").write_bytes(version)
    with (build / "build.stdout").open("wb") as out, (build / "build.stderr").open("wb") as err:
        subprocess.run(command, stdout=out, stderr=err, check=True, timeout=120)
    test_command = [sys.executable, str(root / SOURCES[-1]), str(client), "--count-only-valid"]
    with (build / "release-reproduction-functional.log").open("wb") as out, (build / "protocol.stderr").open("wb") as err:
        subprocess.run(test_command, stdout=out, stderr=err, check=True, timeout=120)
    if (build / "release-reproduction-functional.log").read_text() != SUCCESS or (build / "protocol.stderr").read_bytes():
        raise ValueError("unexpected count-only protocol validation output")
    provenance = dict(revision=revision, source_sha256=source_hashes, binary_sha256=sha(client),
                      source_root=str(root), binary_path=str(client), build_command=command,
                      compiler=dict(path=str(compiler), sha256=sha(compiler), version_sha256=sha(build / "compiler-version.txt")))
    validation = dict(candidate_commit=revision, candidate_source_sha256=source_hashes,
                      candidate_binary_sha256=sha(client), command=test_command, returncode=0,
                      validation=dict(release_candidate_protocol="passed", scope="valid-response count-only loopback; no application or timing evidence"))
    (build / "client-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    (build / "provenance.json").write_text(json.dumps(validation, indent=2) + "\n")
    (build / "COMMANDS.md").write_text("# Current-source client validation\n\nCommands (JSON argument arrays):\n\n" +
                                      json.dumps(command) + "\n\n" + json.dumps(test_command) + "\n")
    return Namespace(**{**vars(args), "client_binary": client, "client_provenance": build / "client-provenance.json",
                        "client_source_root": root, "client_validation_directory": build})
