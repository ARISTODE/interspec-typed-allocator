# Variants of the artifact's analysis (tracker item C2)

The queries that the artifact ships do not reproduce the artifact's own raw
reports or the paper's coverage tables. These variants change one rule each,
to find out which rule accounts for a difference. They are diagnostic: a
variant's output is not a coverage result.

| Variant | Change |
|---|---|
| `without_opacity_rule` | `classOpaqueToTrusted` never holds. In the shipped queries a struct defined in untrusted code whose fields trusted code never reads, and whose definition is not in a trusted file or an `include/` header, is "opaque": the analysis does not go through a pointer to it and does not count its fields. |
| `without_opacity_rule_all_owned_by_t` | The change above, and `classTrustedForOwnership` holds for every struct. In the shipped queries a field counts as T's data sent to U only if the struct that contains it is defined in trusted code; with this change every field reachable from a pointer that T passes counts, including the fields of objects that U allocated and owns. |
| `paper_counting_rule` | **The rule the regenerated tables use (JH decision of 2026-11-14).** `without_opacity_rule`, and in the export step a field counts as an interface field on the T-to-U side whoever owns the object. This is what the paper's coverage section describes: fields reachable from the interface that are not copied to U count under SP1, and fields whose updates are not copied back count under SP2. It includes the fields of objects that U allocates and owns. |
| `paper_counting_rule_regrouped` | `paper_counting_rule`, and the predicate `helperReadsSlotViaInstalledCallback` of `ql/lib/InterCompartmentFlow.qll` is written as a join of helper predicates (`c2CallThroughParamPaths`, `c2InstalledCallbackReads`, `c2CallMatchesInstalledCallback`). The conjuncts are the same and only their grouping under the existential quantifiers changes, so the result is the same. The shipped form ran 53 minutes on ffmpeg/libvpx without finishing (bad join order). Used for the boundaries on which the shipped form does not finish; checked against `paper_counting_rule` on nginx/libpcre (`evaluation/results/tracker/C2/10-…`). |
| `paper_counting_rule_factored` | `paper_counting_rule_regrouped`, and seven predicates of `ql/lib/PointerTargetDomain.qll` (`exprMayTargetU…`, `exprMayTargetT…`, `exprMayTargetNull…` with a `Function` argument) are each written as a part that does not depend on the function and a part that does (`factored.py`). In the shipped form a disjunct that does not mention the function holds for every function of the database, so the relations have (functions) x (expressions) rows: 2.4 billion on ffmpeg/libvpx. The disjuncts are the shipped ones, moved and not changed, so the result is the same. Checked against `paper_counting_rule` on all eight boundaries that finish with it (`evaluation/results/tracker/C2/12-…`). |

The first two variants are diagnostic. `paper_counting_rule` is not: it is the
counting rule of the coverage tables, and the artifact has to ship it (W5).

`scripts/prepare_coverage_query_variant.sh VARIANT WORK VARIANT_WORK` builds a
work directory whose query pack and scripts have the variant applied; then
`scripts/run_coverage_analysis.sh` runs on it unchanged with
`COVERAGE_WORK=VARIANT_WORK`.
| `paper_counting_rule_inlined` | `paper_counting_rule_factored`, and two predicates of the queries are marked `pragma[inline]`: `exprUsesScalarVariableOrAlias` (`scalar_slots_classification.ql`) and `returnSlotAliasVar` (`pointer_slots_classification.ql`). Both take the call `origin` and have a first disjunct that does not mention it, so that disjunct is paired with every call of the database: 3.3 billion rows on nginx/libpcre and 95.8 billion on ffmpeg/libvpx, where the disk filled (`evaluation/results/tracker/C2/13-…`). Each has one caller and that caller binds `origin`; the pragma does not change what holds. Check: `evaluation/results/tracker/C2/14-…`. |
