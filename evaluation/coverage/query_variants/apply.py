#!/usr/bin/env python3
"""Apply one named variant to a copy of the artifact's analysis (C2).

Paths are relative to the analysis root (the directory with `ql/` and
`scripts/`).

Every replacement must match exactly once, so a query pack that differs from
the one this was written against is refused instead of silently left as is.
"""
import sys
from pathlib import Path

VARIANTS = {
    "without_opacity_rule": [
        ("ql/lib/PointerSlotUnified.qll",
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
# The opacity change plus: every struct counts as owned by T for the purpose
# of the T-to-U surface, wherever it is defined.
VARIANTS["without_opacity_rule_all_owned_by_t"] = VARIANTS["without_opacity_rule"] + [
    ("ql/lib/PointerSlotUnified.qll",
     "  predicate classTrustedForOwnership(Class cls) {\n"
     "    PointerBoundaryBase::isTrustedFile(cls.getFile()) or trustedContainerOverride(cls)\n"
     "  }\n",
     "  predicate classTrustedForOwnership(Class cls) {\n"
     "    // C2 diagnostic variant: every struct counts as owned by T.\n"
     "    exists(cls)\n"
     "  }\n"),
]


# The counting rule of the paper's coverage section (JH decision of 2026-11-14):
# every field reachable from an interface parameter counts as an interface
# field, whoever owns the object, and a field that is not copied to U (U does
# not read it) or not copied back (U does not write it) counts as protected.
# The shipped export step counts a field only if T owns it and exposes it.
VARIANTS["paper_counting_rule"] = VARIANTS["without_opacity_rule"] + [
    ("scripts/export_node_policy_surface.py",
     "    return facts.direction_t_to_u and facts.owned_by_t and facts.exposed_to_u\n",
     "    # C2 variant paper_counting_rule: ownership is not required.\n"
     "    return facts.direction_t_to_u\n"),
]


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
