#!/usr/bin/env python3
"""Native unchanged-original-rsync error paths, traced and untraced parity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

CASES = (
    ("rsync", ("--version",), False),
    ("rsync", ("--definitely-not-an-rsync-option",), True),
    ("rsync", ("--daemon", "--definitely-not-an-rsync-option"), True),
    ("tls", ("--definitely-not-a-tls-option",), True),
)


def run(binary, arguments, env):
    proc = subprocess.run([str(binary), *arguments], env=env,
                          text=False, capture_output=True, timeout=12)
    return {"exit_code": proc.returncode,
            "stdout": proc.stdout.decode("utf-8", errors="replace"),
            "stderr": proc.stderr.decode("utf-8", errors="replace")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--traced-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    observations = []
    paths = {name: args.output / f"{name}-original-pointer-events.jsonl"
             for name in ("rsync", "tls")}
    for path in paths.values():
        assert not path.exists(), f"refusing to append: {path}"
    for program, argv, expect_error in CASES:
        baseline_env = dict(os.environ, LC_ALL="C")
        baseline_env.pop("INTERSPEC_RSYNC_ORIGINAL_TRACE", None)
        baseline = run(args.baseline_dir / program, argv, baseline_env)
        traced_env = dict(baseline_env, INTERSPEC_RSYNC_ORIGINAL_TRACE=str(paths[program].resolve()))
        traced = run(args.traced_dir / program, argv, traced_env)
        assert baseline == traced, (program, argv, baseline, traced)
        if expect_error:
            assert baseline["exit_code"] != 0, (program, argv, baseline)
        else:
            assert baseline["exit_code"] == 0, (program, argv, baseline)
        observations.append({"program": program, "argv": list(argv),
                             "exit_code": baseline["exit_code"],
                             "stdout_sha256": hashlib.sha256(baseline["stdout"].encode()).hexdigest(),
                             "stderr_sha256": hashlib.sha256(baseline["stderr"].encode()).hexdigest(),
                             "stderr_excerpt": baseline["stderr"][:240]})
    assert all(p.is_file() and p.stat().st_size for p in paths.values()), \
           "expected original poptStrerror events in both rsync and tls"
    hashes = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths.items()
    }
    output = {"schema": 1,
              "scope": "unchanged-upstream-rsync-native-cli-with-and-without-diagnostic-linker-wrapper",
              "parity": "pass", "cases": observations, "raw_trace_sha256": hashes,
              "binary_sha256": {
                  f"{variant}/{program}": hashlib.sha256(
                      (directory / program).read_bytes()).hexdigest()
                  for variant, directory in (("baseline", args.baseline_dir),
                                             ("traced", args.traced_dir))
                  for program in ("rsync", "tls")}}
    (args.output / "native-parity.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"native_parity": "pass", "cases": len(observations),
                      "raw_trace_sha256": hashes}))


if __name__ == "__main__":
    main()
