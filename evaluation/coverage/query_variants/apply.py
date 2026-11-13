#!/usr/bin/env python3
"""Apply one named change to a copy of the artifact's query pack (C2).

Every replacement must match exactly once, so a query pack that differs from
the one this was written against is refused instead of silently left as is.
"""
import sys
from pathlib import Path

VARIANTS = {
    "without_opacity_rule": [
        ("lib/PointerSlotUnified.qll",
         "  predicate classOpaqueToTrusted(Class cls) {\n"
         "    not PointerBoundaryBase::isTrustedFile(cls.getFile()) and\n"
         "    not classLayoutVisibleToTrusted(cls)\n"
         "  }\n",
         "  predicate classOpaqueToTrusted(Class cls) {\n"
         "    // C2 diagnostic variant without_opacity_rule: no struct is opaque.\n"
         "    none() and exists(cls)\n"
         "  }\n"),
    ],
}


def main():
    variant, pack = sys.argv[1], Path(sys.argv[2])
    for relative, old, new in VARIANTS[variant]:
        path = pack / relative
        text = path.read_text()
        if text.count(old) != 1:
            sys.exit(f"{relative}: expected exactly one occurrence of the text to replace")
        path.write_text(text.replace(old, new))
        print(f"{variant}: changed {relative}")


if __name__ == "__main__":
    main()
