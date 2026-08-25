#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    allocations = []
    uses = []
    types = set()

    with Path(args.csv).open(newline="") as source:
        for row in csv.reader(source):
            if len(row) < 6 or row[0] not in {"allocation", "use"}:
                continue
            kind, name, type_name, function_name, offset, size = row[:6]
            types.add(type_name)
            if kind == "allocation":
                allocations.append({"function": function_name, "type": type_name})
            else:
                uses.append({
                    "name": name,
                    "type": type_name,
                    "offset": int(offset),
                    "bytes": int(size),
                })

    policy = {
        "types": sorted(types),
        "allocations": sorted(allocations, key=lambda x: (x["function"], x["type"])),
        "uses": sorted(uses, key=lambda x: x["name"]),
    }
    Path(args.output).write_text(json.dumps(policy, indent=2) + "\n")


if __name__ == "__main__":
    main()
