# Unresolved pointer fields, split by cause

Follow-up to the integrity table of `18-tables-ten-boundaries/`, asked by JH on
2026-11-16: why does nginx/openssl have 1,971 unresolved pointer fields, and
what does the analysis' `flow_cut` flag mean for `SSL_set_SSL_CTX`.

No new analysis run. `unresolved_causes.py` reads the pointer slot
classification that the analysis runs of this item already produced and applies
the rule of `export_node_policy_surface.py` (interspec-artifact,
`code/analysis/scripts/`): a pointer field needs SP3 when a pointer at or below
it is influenced by U and used by T, and it is resolved when every such pointer
has an expected domain (T, U or null) and is not flagged `flow_cut`. The script
reproduces the table's counts for all three boundaries that have unresolved
fields and adds the cause.

What `flow_cut` is. `pointer_slots_classification.ql` sets it for a slot whose
access path from the parameter has depth 8 or more (`parameterSlotFlowCut`),
and `PointerSlotUnified.qll` enumerates paths only while the parent's depth is
below 8 (`reachablePathWithDepth`). Each dereference, field access and array
element is one step. So the flag marks a pointer at the depth limit of the
analysis: what it points to is not analysed. In the output every flagged slot
has depth exactly 8 and no slot of smaller depth is flagged.

| Boundary | Need SP3 | Resolved | Depth limit only | Unknown domain only | Both | Unresolved |
|---|---:|---:|---:|---:|---:|---:|
| rsync/popt | 23 | 8 | 0 | 15 | 0 | 15 |
| ffmpeg/libvpx | 29 | 18 | 0 | 5 | 6 | 11 |
| nginx/openssl | 2,472 | 501 | 1,009 | 395 | 567 | 1,971 |

nginx/openssl by function (`nginx_openssl.txt`): 10 of 214 functions have
unresolved fields; `SSL_CTX_remove_session` 535, `SSL_free` 436, `HMAC_Init_ex`
376, `SSL_set_SSL_CTX` 273 (all 273 depth limit only), `EVP_EncryptInit_ex` and
`EVP_DecryptInit_ex` 120 each, four others 111. There are 2,443 pointers that
need SP3, 1,318 of them at the depth limit and 771 without an inferred domain
(409 of type `void *`, 266 `char *`); 103 of the 771 have `ex_data` in their
path.

Not done: the 771 pointers without a domain were not traced to source
statements, so the share caused by `NULL` assignments or by getter/setter
interfaces is not known. No run with a larger depth limit was made, so it is
not known how many of the 1,009 fields such a run would resolve.
