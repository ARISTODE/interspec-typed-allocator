#!/usr/bin/env python3
"""Calls per iteration of functions whose name matches a pattern, from two callgrind
profiles of the same program with different iteration counts.
Usage: callgrind_calls.py LOW.callgrind LOW_N HIGH.callgrind HIGH_N REGEX"""
import re, sys, collections
def calls(path):
    names, total, pending = {}, collections.Counter(), None
    for line in open(path, errors="replace"):
        m = re.match(r"c?fn=\((\d+)\)(?: (.*))?", line)
        if m:
            if m.group(2): names[m.group(1)] = m.group(2).strip()
            pending = m.group(1) if line.startswith("cfn=") else None
        elif line.startswith("calls=") and pending:
            total[pending] += int(line[6:].split()[0]); pending = None
    return {names[k]: v for k, v in total.items() if k in names}
low, high = calls(sys.argv[1]), calls(sys.argv[3])
n = int(sys.argv[4]) - int(sys.argv[2])
for name in sorted(high):
    if re.search(sys.argv[5], name):
        d = high[name] - low.get(name, 0)
        if d: print(f"{d / n:10.2f} calls per iteration  {name[:150]}")
