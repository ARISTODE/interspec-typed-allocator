#!/usr/bin/env python3
"""Expected values for the rebuilt YAML parity set (tracker item I3).

Computed with PyYAML's pure-Python parser (yaml.Loader, not the libyaml-based
CLoader), so the expectation does not come from the library under test. The
output is committed before any bench binary is run against it.

Per document: number of parser events, number of scalar events, total UTF-8
bytes of scalar values, and the FNV-1a 64-bit hash over those bytes in order,
chained across parse iterations the way the bench programs chain it.
"""

import argparse
import hashlib
import json
from pathlib import Path

import yaml

FNV_OFFSET, FNV_PRIME, MASK = 1469598103934665603, 1099511628211, (1 << 64) - 1
ITERATIONS = (1, 2)


def describe(data):
    events = scalars = scalar_bytes = 0
    values = []
    for event in yaml.parse(data, Loader=yaml.Loader):
        events += 1
        if isinstance(event, yaml.ScalarEvent):
            scalars += 1
            encoded = event.value.encode("utf-8")
            scalar_bytes += len(encoded)
            values.append(encoded)
    return events, scalars, scalar_bytes, b"".join(values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    assert yaml.Loader.__mro__[1].__module__ == "yaml.reader", "pure-Python loader expected"
    documents = {}
    for path in sorted(args.corpus.glob("*.yaml")):
        data = path.read_bytes()
        events, scalars, scalar_bytes, joined = describe(data)
        per_iteration = {}
        for iterations in ITERATIONS:
            value = FNV_OFFSET
            for _ in range(iterations):
                for byte in joined:
                    value = ((value ^ byte) * FNV_PRIME) & MASK
            per_iteration[str(iterations)] = {
                "events": events * iterations, "scalars": scalars * iterations,
                "scalar_bytes": scalar_bytes * iterations, "hash": f"{value:016x}"}
        documents[path.name] = {"input_bytes": len(data),
                                "sha256": hashlib.sha256(data).hexdigest(),
                                "largest_scalar_bytes": max(
                                    (len(e.value.encode("utf-8"))
                                     for e in yaml.parse(data, Loader=yaml.Loader)
                                     if isinstance(e, yaml.ScalarEvent)), default=0),
                                "expected": per_iteration}
    args.out.write_text(json.dumps(
        {"oracle": f"PyYAML {yaml.__version__} pure-Python parser (yaml.Loader)",
         "documents": documents}, indent=2) + "\n")
    for name, row in documents.items():
        one = row["expected"]["1"]
        print(f"{name}: bytes={row['input_bytes']} events={one['events']} "
              f"scalars={one['scalars']} scalar_bytes={one['scalar_bytes']} hash={one['hash']}")


if __name__ == "__main__":
    main()
