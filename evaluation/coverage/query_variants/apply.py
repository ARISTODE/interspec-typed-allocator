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


# paper_counting_rule_factored, and two predicates of the queries marked
# pragma[inline]. Both have the parameter `FunctionCall origin` and a first
# disjunct that does not mention it, so the evaluator pairs that disjunct with
# every call of the database: (calls) x (uses of variables) rows for
# exprUsesScalarVariableOrAlias, 3.3 billion on nginx/libpcre and 95.8 billion
# on ffmpeg/libvpx. Each has one caller, which binds `origin`. An inlined
# predicate is evaluated inside its caller; the pragma does not change what
# holds.
VARIANTS["paper_counting_rule_inlined"] = VARIANTS["paper_counting_rule_factored"] + [
    ("ql/queries/scalar_slots_classification.ql",
     "predicate exprUsesScalarVariableOrAlias(Expr expr, Variable var, FunctionCall origin) {",
     "pragma[inline]\n"
     "predicate exprUsesScalarVariableOrAlias(Expr expr, Variable var, FunctionCall origin) {"),
    ("ql/queries/pointer_slots_classification.ql",
     "predicate returnSlotAliasVar(FunctionCall origin, Variable baseVar, Variable v) {",
     "pragma[inline]\n"
     "predicate returnSlotAliasVar(FunctionCall origin, Variable baseVar, Variable v) {"),
]


# R5: paper_counting_rule_inlined restricted to the ten OpenSSL functions that
# have unresolved pointer fields at nginx/openssl
# (evaluation/results/tracker/C2/19-unresolved-pointer-fields-by-cause/), with
# the depth limit of the path enumeration as a parameter. The restriction is on
# the two classes from which every query takes its interface parameters and
# returns; with the limit left at 8 the rows of the ten functions must equal
# those of the unrestricted run (checked in the evidence of R5).
R5_FUNCTIONS = ("SSL_CTX_remove_session", "SSL_free", "HMAC_Init_ex", "SSL_set_SSL_CTX",
                "EVP_DecryptInit_ex", "EVP_EncryptInit_ex", "SSL_CTX_use_certificate",
                "SSL_CTX_use_PrivateKey", "SSL_set_session", "ASN1_TIME_print")
_R5_RESTRICTION = [
    ("ql/lib/PointerBoundaryBase.qll",
     "  class BoundaryParameter extends Parameter {\n"
     "    BoundaryParameter() {\n"
     "      interfaceDirection(this.getFunction(), _)\n"
     "    }\n",
     "  // R5 variant: only these interface functions.\n"
     "  predicate r5Function(Function f) {\n"
     "    f.getName() in [" + ", ".join(f'"{name}"' for name in R5_FUNCTIONS) + "]\n"
     "  }\n\n"
     "  class BoundaryParameter extends Parameter {\n"
     "    BoundaryParameter() {\n"
     "      interfaceDirection(this.getFunction(), _) and r5Function(this.getFunction())\n"
     "    }\n"),
    ("ql/lib/PointerBoundaryBase.qll",
     "      ) and interfaceDirection(this, _)\n"
     "    }\n",
     "      ) and interfaceDirection(this, _) and r5Function(this)\n"
     "    }\n"),
]


def _r5_depth(limit):
    """Every occurrence of the limit 8, with the number of occurrences expected."""
    return [("all", "ql/lib/PointerSlotUnified.qll", "parentDepth < 8", f"parentDepth < {limit}", 3),
            ("all", "ql/lib/ScalarSlotUnified.qll", "parentDepth < 8", f"parentDepth < {limit}", 3),
            ("all", "ql/queries/pointer_slots_classification.ql", "depth >= 8", f"depth >= {limit}", 3),
            ("all", "ql/queries/scalar_slots_classification.ql", "depth >= 8", f"depth >= {limit}", 5)]


VARIANTS["r5_ten_functions"] = VARIANTS["paper_counting_rule_inlined"] + _R5_RESTRICTION


# SP3's dereference condition (Condition B of the paper) with the shipped opacity
# test. The tables count every field reachable from the interface (paper counting
# rule, which switches the opacity rule off), and T's use of a slot below a pointer
# that T passes is then approximated by "the write can escape" (slotUsedByTrustedViaEscape),
# so a pointer deep inside an object of U, such as OpenSSL's SSL or SSL_CTX, counts
# as dereferenced by T. T cannot read a field of a class whose fields it never
# accesses and whose definition it cannot see (the shipped classOpaqueToTrusted),
# so it cannot dereference a pointer stored there through this path; a getter that
# returns such a pointer is an interface function of its own and is classified as such.
# Only the T-use condition of SP3 changes; SP1 and SP2 are computed as before.
_SP3_OPACITY = [
    ("ql/lib/PointerSlotUnified.qll",
     "  predicate classOpaqueToTrusted(Class cls) {\n"
     "    // C2 diagnostic variant without_opacity_rule: no struct is opaque.\n"
     "    none() and exists(cls)\n"
     "  }\n",
     "  predicate classOpaqueToTrusted(Class cls) {\n"
     "    // C2 diagnostic variant without_opacity_rule: no struct is opaque.\n"
     "    none() and exists(cls)\n"
     "  }\n"
     "\n"
     "  /** Variant sp3_opacity: the shipped opacity test, used only for SP3's trusted-use condition. */\n"
     "  predicate classOpaqueToTrustedForSP3(Class cls) {\n"
     "    not PointerBoundaryBase::isTrustedFile(cls.getFile()) and\n"
     "    not classLayoutVisibleToTrusted(cls)\n"
     "  }\n"),
    ("ql/queries/pointer_slots_classification.ql",
     "  parameterSlotUInfluenced(p, direction, slotPath) and\n"
     "  pointerSlotUsedByTrustedForSP3(p, slotPath)\n"
     "}\n",
     "  parameterSlotUInfluenced(p, direction, slotPath) and\n"
     "  pointerSlotUsedByTrustedForSP3(p, slotPath) and\n"
     "  not slotInsideClassOpaqueToTrusted(p, slotPath)\n"
     "}\n"
     "\n"
     "/**\n"
     " * Variant sp3_opacity: the slot is a field, or lies below a field, of an object whose\n"
     " * class T never accesses and whose definition T cannot see. T cannot read such a\n"
     " * field, so it cannot dereference a pointer stored in it through this path.\n"
     " */\n"
     "bindingset[p, slotPath]\n"
     "predicate slotInsideClassOpaqueToTrusted(PointerBoundaryBase::BoundaryParameter p, string slotPath) {\n"
     "  exists(int i, string objPath, Type t, Class cls |\n"
     "    i = slotPath.indexOf(\"/field:\") and\n"
     "    objPath = slotPath.prefix(i) and\n"
     "    PointerSlotUnified::reachablePath(p, objPath, t) and\n"
     "    PointerSlotUnified::classType(t, cls) and\n"
     "    PointerSlotUnified::classOpaqueToTrustedForSP3(cls)\n"
     "  )\n"
     "}\n"),
]
VARIANTS["paper_counting_rule_sp3_opacity"] = VARIANTS["paper_counting_rule_inlined"] + _SP3_OPACITY


# The same restriction with the plain form of Condition B: a pointer stored in an
# object counts as dereferenced by T only if T's code accesses some field of the
# object's class (and the class is not defined in T). Unlike the shipped opacity
# test, it does not treat a class as visible only because its definition is in a
# public include header: OpenSSL's ASN1_STRING is public, but nginx handles it
# only through ASN1_STRING_length and ASN1_STRING_data.
_SP3_FIELD_ACCESS = [
    ("ql/lib/PointerSlotUnified.qll",
     "  predicate classOpaqueToTrusted(Class cls) {\n"
     "    // C2 diagnostic variant without_opacity_rule: no struct is opaque.\n"
     "    none() and exists(cls)\n"
     "  }\n",
     "  predicate classOpaqueToTrusted(Class cls) {\n"
     "    // C2 diagnostic variant without_opacity_rule: no struct is opaque.\n"
     "    none() and exists(cls)\n"
     "  }\n"
     "\n"
     "  /** Variant sp3_field_access: T's code accesses no field of this class, which T does not define. */\n"
     "  predicate classFieldsNotAccessedByTrusted(Class cls) {\n"
     "    not PointerBoundaryBase::isTrustedFile(cls.getFile()) and\n"
     "    not trustedFieldVisibleToTrusted(cls)\n"
     "  }\n"),
    ("ql/queries/pointer_slots_classification.ql",
     "  parameterSlotUInfluenced(p, direction, slotPath) and\n"
     "  pointerSlotUsedByTrustedForSP3(p, slotPath)\n"
     "}\n",
     "  parameterSlotUInfluenced(p, direction, slotPath) and\n"
     "  pointerSlotUsedByTrustedForSP3(p, slotPath) and\n"
     "  not slotInsideClassNotAccessedByTrusted(p, slotPath)\n"
     "}\n"
     "\n"
     "/**\n"
     " * Variant sp3_field_access: the slot is a field, or lies below a field, of an object\n"
     " * whose class T's code never accesses. T cannot load a pointer from such a field, so\n"
     " * it cannot dereference it through this path (Condition B).\n"
     " */\n"
     "bindingset[p, slotPath]\n"
     "predicate slotInsideClassNotAccessedByTrusted(PointerBoundaryBase::BoundaryParameter p, string slotPath) {\n"
     "  exists(int i, string objPath, Type t, Class cls |\n"
     "    i = slotPath.indexOf(\"/field:\") and\n"
     "    objPath = slotPath.prefix(i) and\n"
     "    PointerSlotUnified::reachablePath(p, objPath, t) and\n"
     "    PointerSlotUnified::classType(t, cls) and\n"
     "    PointerSlotUnified::classFieldsNotAccessedByTrusted(cls)\n"
     "  )\n"
     "}\n"),
]
VARIANTS["paper_counting_rule_sp3_field_access"] = VARIANTS["paper_counting_rule_inlined"] + _SP3_FIELD_ACCESS
for _limit in (10, 12, 16):
    VARIANTS[f"r5_ten_functions_depth_{_limit}"] = VARIANTS["r5_ten_functions"] + _r5_depth(_limit)


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
        if change[0] == "all":
            _, relative, old, new, expected = change
            path = pack / relative
            text = path.read_text()
            if text.count(old) != expected:
                sys.exit(f"{relative}: expected {expected} occurrences of {old!r}, found {text.count(old)}")
            path.write_text(text.replace(old, new))
            print(f"{variant}: changed {relative} ({expected} occurrences)")
            continue
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
