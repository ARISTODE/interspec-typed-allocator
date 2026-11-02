#!/usr/bin/env python3
"""Black-box protocol parity for original Memcached versus deployed isolation.

This script does not instrument, create, or count upstream pointer expressions.
It reuses the original-source native workload identically for all variants.
"""
import argparse
import hashlib
import json
from pathlib import Path
from run_memcached_native_origin import exercise

VARIANTS = ("native", "rlbox-only", "tracked-no-check", "interspec")


def run(work, output):
    output.mkdir(parents=True, exist_ok=True)
    binaries = {name: work / "bin" / ("memcached-" + name)
                for name in VARIANTS}
    absent = [str(path) for path in binaries.values() if not path.is_file()]
    if absent:
        raise RuntimeError("missing actual server binaries: " + repr(absent))

    observations = {}
    errors = {}
    for name, binary in binaries.items():
        try:
            # Same original application protocol interactions; instrumentation
            # disabled, so diagnostic helpers are not counted as source sites.
            observations[name] = exercise(binary, output / "logs" / name, None)
        except (AssertionError, RuntimeError, OSError, EOFError, TimeoutError) as exc:
            errors[name] = repr(exc)
    reference = observations.get("native")
    if reference is None:
        raise RuntimeError("native original Memcached workload did not pass: " +
                           errors.get("native", "missing reference"))

    equal = {name: (name in observations and observations[name] == reference)
             for name in VARIANTS}
    report = {
        "schema": 1,
        "scope": "identical original application Memcached protocol workload across pinned native and sandbox variants",
        "not_a_pointer_count": True,
        "native_isolated_parity": "pass" if all(equal.values()) else "mismatch",
        "response_equality": equal,
        "observations": observations,
        "workload_errors": errors,
        "reference_response_count": len(reference),
        "binary_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for name, path in binaries.items()},
        "limits": [
            "This checks the exercised protocol and watch events, not all application behavior.",
            "No pointer provenance or raw T/U address transit is inferred.",
            "No project-authored wrapper pointer is counted as an upstream source site.",
        ],
    }
    (output / "native-versus-isolated.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({
        "native_isolated_parity": report["native_isolated_parity"],
        "response_equality": equal,
        "reference_response_count": len(reference),
        "workload_errors": errors,
    }, sort_keys=True))
    if not all(equal.values()):
        print("::warning::Original Memcached protocol outputs differ from an "
              "isolated variant; see native-versus-isolated.json")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path,
                   default=Path("/tmp/interspec-memcached-deployment"))
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    run(args.work, args.out)


if __name__ == "__main__":
    main()
