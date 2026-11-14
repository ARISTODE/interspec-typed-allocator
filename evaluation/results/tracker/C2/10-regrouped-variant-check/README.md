# C2: check of the query variant `paper_counting_rule_regrouped`

The variant (`evaluation/coverage/query_variants/apply.py`) is
`paper_counting_rule` with one predicate of the artifact's pointer library,
`InterCompartmentFlow::helperReadsSlotViaInstalledCallback`, written as a join
of three helper predicates. The conditions are the same; only their grouping
under the existential quantifiers changes, which cannot change the result.
Reason for the change: on ffmpeg/libvpx the shipped form ran 53 minutes on
inputs of 160 and 139,668 rows without finishing
(`../09-large-boundaries/c-ffmpeg_libvpx-database-ffmpeg_vpx_only-stopped/`).

Two boundaries were run again with the variant and every CSV file compared with
the output of `paper_counting_rule` (SHA-256 of all twelve files, `csv-sha256.txt`).

| Directory | Compared with | Rows of the predicate | Result |
|---|---|---:|---|
| `a-nginx_libpcre/` | `../09-large-boundaries/b-nginx_libpcre-database-nginx_pcre/` | 0 in both forms | 12 of 12 files identical. Shows only that the variant compiles and leaves the rest alone. |
| `b-yaml_libyaml/` | `../08-paper-counting-rule-6ec6b97/yaml_libyaml/` | 14 in both forms (helper predicates: 5, 24 and 18 rows) | 12 of 12 files identical. |

yaml/libyaml is the only finished boundary on which the predicate has rows
(evaluator logs of the earlier runs: magick/libpng and zip/libzip 0 rows, the
others have no installed callback at all). The check on one boundary supports
the argument from the form of the predicate; it does not replace it.

The scratch directory in `command.txt` and `analysis.log` is written as `$S`.
