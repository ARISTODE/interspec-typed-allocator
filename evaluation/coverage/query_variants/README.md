# Variants of the artifact's queries (tracker item C2)

The queries that the artifact ships do not reproduce the artifact's own raw
reports or the paper's coverage tables. These variants change one rule each,
to find out which rule accounts for a difference. They are diagnostic: a
variant's output is not a coverage result.

| Variant | Change |
|---|---|
| `without_opacity_rule` | `classOpaqueToTrusted` never holds. In the shipped queries a struct defined in untrusted code whose fields trusted code never reads, and whose definition is not in a trusted file or an `include/` header, is "opaque": the analysis does not go through a pointer to it and does not count its fields. |
| `without_opacity_rule_all_owned_by_t` | The change above, and `classTrustedForOwnership` holds for every struct. In the shipped queries a field counts as T's data sent to U only if the struct that contains it is defined in trusted code; with this change every field reachable from a pointer that T passes counts, including the fields of objects that U allocated and owns. |

`scripts/prepare_coverage_query_variant.sh VARIANT WORK VARIANT_WORK` builds a
work directory whose query pack has the change applied; then
`scripts/run_coverage_analysis.sh` runs on it unchanged with
`COVERAGE_WORK=VARIANT_WORK`.
