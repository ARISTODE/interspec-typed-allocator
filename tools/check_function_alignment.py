#!/usr/bin/env python3
"""Usage: check_function_alignment.py [--prefix P] [--min-size N] BINARY...

Checks that the functions of each binary whose name starts with P (default
w2c_, the code that wasm2c generates for the sandboxed library) and whose size
is at least N bytes (default 256) start on a 64-byte boundary. Parts that the
compiler splits off as NAME.cold are skipped: the compiler does not align them
and they hold code that the measured workloads do not run.

Prints one line per binary with the number of functions checked and the number
not aligned, then the names of up to ten that are not. Exits 1 if any function
is not aligned or if a binary has no function with the prefix.
"""
import subprocess
import sys


def main():
    args = sys.argv[1:]
    prefix, min_size = "w2c_", 256
    while args and args[0].startswith("--"):
        if args[0] == "--prefix":
            prefix = args[1]
        elif args[0] == "--min-size":
            min_size = int(args[1])
        else:
            sys.exit(__doc__)
        args = args[2:]
    if not args:
        sys.exit(__doc__)
    failed = False
    for binary in args:
        out = subprocess.run(["nm", "-S", "--defined-only", binary], check=True,
                             capture_output=True, text=True).stdout
        checked, bad = 0, []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) != 4 or parts[2] not in "tT":
                continue
            address, size, name = int(parts[0], 16), int(parts[1], 16), parts[3]
            if not name.startswith(prefix) or ".cold" in name or size < min_size:
                continue
            checked += 1
            if address % 64:
                bad.append(name)
        print(f"{binary}: {checked} functions checked, {len(bad)} not on a 64-byte boundary")
        for name in bad[:10]:
            print(f"  {name}")
        failed = failed or bool(bad) or checked == 0
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
