# R6: inferred, checked and exercised SP3 fields

Tracker item R6 in `EVAL_TRACKER.md`.

`SP3_FIELD_STATUS.md` is written by `tools/render_sp3_field_status.py`:

    python3 tools/render_sp3_field_status.py \
      --artifact-reports ../interspec-artifact/data/raw/policy_reports \
      --records evaluation/coverage/sp3_metadata_sources.json \
      --status evaluation/coverage/sp3_field_status.json --root . \
      --out evaluation/results/tracker/R6/SP3_FIELD_STATUS.md

(`interspec-artifact` at `2b2d2fd`.) The three columns come from three
different sources, and the tool fails if one of them does not support a row:

| Column | Source | What the tool verifies |
|---|---|---|
| Inferred | `sp3_cases.csv` of the artifact's analysis output | the case exists in the file |
| Checked | the wrapper's source in `integration/` | the text of the check named in `sp3_field_status.json` occurs in the file; the line is printed |
| Exercised | raw output of the measurements: callgrind profiles of the InterSpec build (calls of the library function, difference quotient over two iteration counts), or the registry trace of the deployment test for the two servers | the number is counted from the profile or the trace |

The list of fields (31) and the join between a case of the artifact and a field
of a port are those of C3 (`evaluation/coverage/sp3_metadata_sources.json`).
`sp3_field_status.json` adds, per field, where the check is and which function
or trace event shows that the workload reaches it; these two entries are
written by hand and verified by the tool as described.

## Result

| | Fields |
|---|---:|
| Inferred by the analysis, on the 8 boundaries whose case file can be joined | 24 |
| of these, checked by a wrapper | 13 |
| Checked by a wrapper, all 10 boundaries | 20 |
| of these, reached by the measured workload | 19 |
| Checked by a wrapper without a case of the analysis, on the 8 boundaries | 4 |
| Checked by a wrapper on the 2 boundaries without a joined case file | 3 |

Two boundaries cannot be joined: the artifact has no `sp3_cases.csv` for
ffmpeg/libvpx (the paper's table counts 2 fields there, which the artifact
does not let me check), and for nginx/openssl the case file is not joined for
the reason recorded in C3. So for 3 of the 20 checked fields (2 of
ffmpeg/libvpx, the `ex_data` pointer of nginx/openssl) this table does not say
whether the analysis infers them. The first version of this file (commit
`7cdf80f`) counted the 2 of ffmpeg/libvpx as "not inferred" and gave 9
boundaries and 7 fields without a case; that was wrong and is corrected here.

- The one checked field that no measured workload reaches is the return value
  of `poptBadOption` (rsync/popt): the file synchronization passes only valid
  options. `tools/test_rsync_policy_switches.py` runs rsync with an invalid
  option and reaches it.
- 11 inferred fields are not checked. For 3 the port keeps the pointer inside U
  or the array pointer does not cross (`png_get_io_ptr`, `native_write_cb`,
  `poptGetArgs` return), so there is nothing to check. For the other 8 the
  port does not wrap the function or does not pass the pointer
  (`item_trylock_unlock`, `thread_setname`, `ngx_regex_free`, `poptStrerror`,
  two fields of `poptDupArgv`, `ucl_parser_get_error`, `zip_error_strerror`).
  None of these 8 is reached by a measured workload through a port; an
  application that uses them would need the wrapper extended.
- 4 checked fields on the joined boundaries have no case in the analysis
  output and were written by hand: the 2 return values of the magick/libpng
  shim (fields of the port's own interface functions), the option-table
  strings of rsync/popt and the name table of nginx/libpcre.

## Can the libpcre name table be inferred?

Not by the current analysis. The name table reaches T through the third
parameter of `pcre2_pattern_info`, which is declared `void *`: U writes a
pointer through it after a cast that depends on the second parameter (`what`).
The analysis has one row for this parameter
(`pointer_slots_classification.csv`: `pcre2_pattern_info_8,param,2,T_TO_U,,void *`,
read by U, not written), because it enumerates the fields of a pointer by its
declared type, and `void` has none. The pointer that U stores through the cast
is therefore not a field of the interface for the analysis, and no SP3 case is
produced. Inferring it would need the analysis to follow the cast per value of
`what`, which it does not do. The check in the port
(`integration/nginx_server/bridge.cpp`, `Use::names`) stays hand-written. The
paper's paragraph on manual effort does not say this yet; R7 adds the counts
of this file to it.

## Limits of the "exercised" column

- It shows that the wrapper function with the check runs in the measured
  workload, not how often the check itself passes or fails.
- The profiles and traces are those of the binaries at `930cb20`
  (`../R1/03-campaign-930cb20/`, `../R3/01-vm-00a20ec/`). The number of calls
  is a property of the workload and does not depend on the registry change
  that follows.
- For memcached and nginx the trace is that of the deployment test, which
  sends the request types of the timed workload, not the timed run itself
  (tracing is compiled out of the timed binaries).
