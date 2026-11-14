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

The first two variants are diagnostic. `paper_counting_rule` is not: it is the
counting rule of the coverage tables, and the artifact has to ship it (W5).

`scripts/prepare_coverage_query_variant.sh VARIANT WORK VARIANT_WORK` builds a
work directory whose query pack and scripts have the variant applied; then
`scripts/run_coverage_analysis.sh` runs on it unchanged with
`COVERAGE_WORK=VARIANT_WORK`.
