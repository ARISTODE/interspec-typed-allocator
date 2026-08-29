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
            if len(row) < 6 or row[0] not in {"allocation", "use", "dynamic_use"}:
                continue
            kind, name, type_name, function_name, offset, size = row[:6]
            types.add(type_name)
            if kind == "allocation":
                allocation = {"function": function_name, "type": type_name}
                if len(row) >= 10:
                    start_line, start_column, end_line, end_column = map(
                        int, row[6:10]
                    )
                    if min(start_line, start_column, end_line, end_column) > 0:
                        allocation["site"] = {
                            "start_line": start_line,
                            "start_column": start_column,
                            "end_line": end_line,
                            "end_column": end_column,
                        }
                allocations.append(allocation)
            else:
                use = {
                    "name": name,
                    "type": type_name,
                    "offset": int(offset),
                }
                if kind == "dynamic_use":
                    use["dynamic_bytes"] = True
                else:
                    use["bytes"] = int(size)
                uses.append(use)

    def allocation_key(allocation):
        site = allocation.get("site", {})
        return (
            allocation["function"],
            allocation["type"],
            site.get("start_line", 0),
            site.get("start_column", 0),
        )

    policy = {
        "types": sorted(types),
        "allocations": sorted(allocations, key=allocation_key),
        "uses": sorted(uses, key=lambda x: x["name"]),
    }
    Path(args.output).write_text(json.dumps(policy, indent=2) + "\n")


if __name__ == "__main__":
    main()
