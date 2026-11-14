#!/usr/bin/env python3
"""Apply one named variant to a copy of the artifact's analysis (C2).

Paths are relative to the analysis root (the directory with `ql/` and
`scripts/`).

Every replacement must match exactly once, so a query pack that differs from
the one this was written against is refused instead of silently left as is.
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import factored  # noqa: E402

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


# paper_counting_rule with one predicate of the pointer library written as a
# join of two helper predicates. The conjuncts are the same; they are grouped
# so that the evaluator joins the small relations first. On ffmpeg/libvpx the
# shipped form ran for 53 minutes on inputs of 160 and 139,668 rows without
# finishing (C2/09-large-boundaries/c-...). A regrouping of conjuncts under
# their existential quantifiers cannot change the result; the outputs on
# nginx/libpcre are compared file by file as a check.
_OLD_INSTALLED_CALLBACK = """  predicate helperReadsSlotViaInstalledCallback(Parameter param, string path) {
    PointerBoundaryBase::isUntrustedFile(param.getFunction().getFile()) and
    exists(ExprCall call, int argIndex, string callbackPath, string contextPath, Parameter setupParam,
           Function callbackTarget, Parameter callbackContextParam, string contextSourcePath, string callbackSubPath |
      call.getEnclosingFunction() = param.getFunction() and
      PointerSlotUnified::exprPathForParameter(param, call.getExpr(), callbackPath) and
      PointerSlotUnified::exprPathForParameter(param, call.getArgument(argIndex), contextPath) and
      samePointerPointeeType(param, setupParam) and
      installedCallbackOnParam(setupParam, callbackPath, callbackTarget, contextPath, contextSourcePath) and
      callbackContextParam = callbackTarget.getParameter(argIndex) and
      exists(Type t, PointerType pt |
        t = callbackContextParam.getType() and PointerSlotUnified::pointerType(t, pt)
      ) and
      helperReadsSlotDepth2(callbackContextParam, callbackSubPath) and
      (
        contextSourcePath = "" and path = callbackSubPath
        or contextSourcePath != "" and path = contextSourcePath + callbackSubPath
      )
    )
  }
"""
_NEW_INSTALLED_CALLBACK = """  // C2 variant paper_counting_rule_regrouped: the conjuncts of the shipped
  // predicate, grouped into two helper predicates. Same result.
  pragma[nomagic]
  predicate c2CallThroughParamPaths(Parameter param, string callbackPath, string contextPath, int argIndex) {
    PointerBoundaryBase::isUntrustedFile(param.getFunction().getFile()) and
    exists(ExprCall call |
      call.getEnclosingFunction() = param.getFunction() and
      PointerSlotUnified::exprPathForParameter(param, call.getExpr(), callbackPath) and
      PointerSlotUnified::exprPathForParameter(param, call.getArgument(argIndex), contextPath)
    )
  }

  pragma[nomagic]
  predicate c2InstalledCallbackReads(
    Parameter setupParam, string callbackPath, string contextPath, int argIndex, string path
  ) {
    exists(Function callbackTarget, Parameter callbackContextParam, string contextSourcePath, string callbackSubPath |
      installedCallbackOnParam(setupParam, callbackPath, callbackTarget, contextPath, contextSourcePath) and
      callbackContextParam = callbackTarget.getParameter(argIndex) and
      exists(Type t, PointerType pt |
        t = callbackContextParam.getType() and PointerSlotUnified::pointerType(t, pt)
      ) and
      helperReadsSlotDepth2(callbackContextParam, callbackSubPath) and
      (
        contextSourcePath = "" and path = callbackSubPath
        or contextSourcePath != "" and path = contextSourcePath + callbackSubPath
      )
    )
  }

  pragma[nomagic]
  predicate c2CallMatchesInstalledCallback(Parameter param, Parameter setupParam, string path) {
    exists(string callbackPath, string contextPath, int argIndex |
      c2CallThroughParamPaths(param, callbackPath, contextPath, argIndex) and
      c2InstalledCallbackReads(setupParam, callbackPath, contextPath, argIndex, path)
    )
  }

  predicate helperReadsSlotViaInstalledCallback(Parameter param, string path) {
    exists(Parameter setupParam |
      c2CallMatchesInstalledCallback(param, setupParam, path) and
      samePointerPointeeType(param, setupParam)
    )
  }
"""
VARIANTS["paper_counting_rule_regrouped"] = VARIANTS["paper_counting_rule"] + [
    ("ql/lib/InterCompartmentFlow.qll", _OLD_INSTALLED_CALLBACK, _NEW_INSTALLED_CALLBACK),
]


# paper_counting_rule_regrouped, and seven predicates of the target-domain
# library factored into a part that does not depend on the function argument
# and a part that does (factored.py). Same results; without it the relations
# have (functions in the database) x (expressions) rows.
VARIANTS["paper_counting_rule_factored"] = VARIANTS["paper_counting_rule_regrouped"] + [
    ("predicate", "ql/lib/PointerTargetDomain.qll", name, sha256, new)
    for name, (sha256, new) in factored.PREDICATES.items()
]


def predicate_block(text, relative, name):
    """The text of predicate `name`: from `  predicate NAME(` to the next `  }` line."""
    start = "  predicate " + name + "("
    if text.count(start) != 1:
        sys.exit(f"{relative}: expected exactly one definition of {name}")
    begin = text.index(start)
    end = text.index("\n  }\n", begin) + len("\n  }\n")
    return text[begin:end]


def main():
    variant, pack = sys.argv[1], Path(sys.argv[2])
    for change in VARIANTS[variant]:
        if change[0] == "predicate":
            _, relative, name, sha256, new = change
            path = pack / relative
            text = path.read_text()
            old = predicate_block(text, relative, name)
            if hashlib.sha256(old.encode()).hexdigest() != sha256:
                sys.exit(f"{relative}: predicate {name} differs from the one this variant was written against")
        else:
            relative, old, new = change
            path = pack / relative
            text = path.read_text()
        if text.count(old) != 1:
            sys.exit(f"{relative}: expected exactly one occurrence of the text to replace")
        path.write_text(text.replace(old, new))
        print(f"{variant}: changed {relative}")


if __name__ == "__main__":
    main()
