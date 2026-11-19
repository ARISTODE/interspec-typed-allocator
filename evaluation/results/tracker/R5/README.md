# R5: unresolved pointer fields at nginx/openssl

Tracker item R5 in `EVAL_TRACKER.md`. Analysis runs, not timings. Machine:
the Claude Code cloud VM (4 vCPUs, 16 GB); CodeQL bundle of the coverage
items (C2). `interspec-artifact` is read-only for this session, so the query
changes are variants in this repository
(`evaluation/coverage/query_variants/apply.py`): `r5_ten_functions` restricts
the interface to the 10 OpenSSL functions that have unresolved fields, and
`r5_ten_functions_depth_N` also sets the depth limit of the path enumeration
to N. The counting rule is that of the coverage tables.

| Path | Content |
|---|---|
| `limit-8/` | The 10 functions with the limit of the paper (8). 55 minutes. Reproduces the counts of the full run for these functions. |
| `limit-10/` | The same with a limit of 10. 78 minutes. |
| `limit-12/` | The same with a limit of 12. 115 minutes. |
| `limit-10-interrupted/` | A first run with limit 10 that a container restart ended on 2026-11-18; no result. |
| `slot-writes-2/` | `evaluation/coverage/queries/r5_slot_writes.ql` on the limit-8 pack: every assignment that the target-domain rules can see for a pointer slot of the 10 functions (in the interface function or within three calls in U), with the kind of its right-hand side and whether a rule classifies it. 758 rows. |
| `slot-writes/` | The first run of that query. It ran in the default pack, whose generated configuration is another benchmark, and returned no rows. Kept; not a result. |
| `compare.py`, `compare-limit-8-10.txt`, `compare-limit-8-12.txt` | The comparisons below and their output. |
| `steps.txt`, `chain5.log`, `r5-run.sh`, `r5-slot.py`, `chain3.sh`, `chain5.sh` | Step logs with start, end and exit status, and the drivers. |

The classification files are stored compressed
(`nginx_openssl/pointer_slots_classification.csv.gz`).

```bash
python3 compare.py <(zcat limit-8/nginx_openssl/pointer_slots_classification.csv.gz) \
  <(zcat limit-10/nginx_openssl/pointer_slots_classification.csv.gz) slot-writes-2/r5_slot_writes.csv
```

## A larger depth limit

Pointer fields of the 10 functions that need SP3, by class (classes as in
`../C2/19-unresolved-pointer-fields-by-cause/`):

| | Limit 8 | Limit 10 | Limit 12 |
|---|---:|---:|---:|
| Need SP3 | 2,440 | 6,461 | 16,888 |
| Resolved | 469 | 1,689 | 5,400 |
| Depth limit only | 1,009 | 2,222 | 4,436 |
| Unknown domain only | 395 | 1,320 | 3,981 |
| Both | 567 | 1,230 | 3,071 |
| Unresolved | 1,971 | 4,772 | 11,488 |
| Analysis time | 55 min | 78 min | 115 min |

The 1,971 are the unresolved fields of the paper's table for this boundary.
What happens at limit 10 to the fields of limit 8:

| Class at limit 8 | Resolved | Depth limit only | Unknown domain only | Both |
|---|---:|---:|---:|---:|
| Depth limit only (1,009) | 523 | 260 | 0 | 226 |
| Both (567) | 0 | 0 | 448 | 119 |
| Unknown domain only (395) | 0 | 0 | 392 | 3 |
| Resolved (469) | 371 | 4 | 60 | 34 |

- A larger limit resolves about half of the fields that were unresolved only
  because of the limit (523 of 1,009). The other half reaches the new limit
  (260) or leads to a pointer without an inferred domain (226).
- It does not reduce the number of unresolved fields. The objects behind the
  old limit contain further pointers: the run reaches 4,021 pointers that need
  SP3 and did not exist at limit 8, 2,802 of them at the new limit and 1,268
  without a domain. Unresolved fields go from 1,971 to 4,772; the resolved
  share goes from 19% to 26%.
- 98 fields that were resolved at limit 8 are not resolved at limit 10: the
  deeper run finds pointers below them that need SP3.
- Of the 1,318 pointers at the limit of 8, 911 have a domain at limit 10 and
  407 do not.

So the paper cannot say that a larger limit would resolve the 1,009 fields.
It now says what this run shows.

With a limit of 12 (`compare-limit-8-12.txt`), the same picture is stronger:

| Class at limit 8 | Resolved | Depth limit only | Unknown domain only | Both |
|---|---:|---:|---:|---:|
| Depth limit only (1,009) | 570 | 187 | 111 | 141 |
| Both (567) | 0 | 0 | 448 | 119 |
| Unknown domain only (395) | 0 | 0 | 390 | 5 |
| Resolved (469) | 364 | 11 | 37 | 57 |

570 of the 1,009 depth-limited fields are resolved at limit 12 (523 at
limit 10), and the unresolved fields grow to 11,488: the run reaches 14,448
pointers that need SP3 and did not exist at limit 8, 5,909 of them at the new
limit and 4,916 without a domain. The resolved share is 32% (19% at limit 8,
26% at limit 10). No run with a limit of 16 was made; the variant exists.

## The 771 pointers without an inferred domain (limit 8)

- **765 are not assigned by U at all.** They count as influenced by U because
  they lie behind a pointer that U writes: the rule
  (`parameterSlotUInfluenced` in `pointer_slots_classification.ql`) marks every
  slot that is reached by dereferencing a written pointer. For 766 of the 771
  the slot-write query finds no assignment in the interface function or within
  three calls, so the target-domain rules have nothing to classify.
- **They lie behind 27 written pointers.** The largest: `ssl->ctx` in
  `SSL_free` (167), `ctx->session_cache_head` and `ctx->session_cache_tail` in
  `SSL_CTX_remove_session` (145 each), `ctx->cipher` (31) and `ctx->engine`
  (27) in each of `EVP_EncryptInit_ex` and `EVP_DecryptInit_ex`.
- **6 are written by U itself.** For 5 of them the query finds the
  assignments, and no rule classifies them: literals (2), a literal and the
  result of a call through a function pointer (2), a pointer field (1).
- Types: `void *` 409, `char *` 266, `unsigned char *` 65, others 31.

The paper said that `NULL` assignments and opaque getter/setter interfaces
are two patterns that cause the unknown domains. The runs show `NULL`-like
literals for 4 of the 771 pointers, so that sentence is replaced by the
finding above. The getter/setter pattern (`ex_data`, 103 of the 771 have
`ex_data` in their path, `../C2/19-…/README.md`) stays as the paper's second
pattern; these runs do not test it separately.
