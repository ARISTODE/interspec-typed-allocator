# C3: metadata sources for full SP3

Tracker item C3 in `EVAL_TRACKER.md`.

`01-table/` is the output of

    python3 tools/render_sp3_metadata_table.py \
      --artifact-reports <interspec-artifact>/data/raw/policy_reports \
      --records evaluation/coverage/sp3_metadata_sources.json \
      --out evaluation/results/tracker/C3/01-table

`SP3_METADATA_SOURCES.md` there is the table; the CSV has the same rows. The
script refuses to run if a case in the artifact's files has no record or a
record names a case that does not exist.

## What the table covers and what it cannot

The paper counts 32 SP3 fields and 11 with unknown expected domain. The
artifact's `sp3_cases.csv` files identify 24 of the 32 by function and slot
(eight boundaries). For the others the artifact gives no list:

- ffmpeg/libvpx: no case file; the paper counts 2. The table lists the two
  fields the port checks.
- magick/libpng: the case file has 2 rows; the paper counts 3. Both rows are
  for callbacks that the artifact's analysis places in T; in the artifact's
  own shim, and in the port, the callbacks are inside U. The table adds the two
  buffers the port checks.
- nginx/openssl: the case file has 196 rows; the paper counts 5 and 11
  unknown. Nothing in the artifact says which 16 rows are meant, and the
  isolated TLS bridge has no pointer crossing at all.

So the table gives expected domain, type source and bounds source for 30
fields: the 24 the artifact identifies and 6 that only the ports have. 17 are
checked by a port. Of the 13 that are not, 4 are memcached/hash (not at the
run-time boundary, I9), 3 do not cross the boundary in the port's wrapper
design, and 6 belong to calls a port does not make or does not isolate.

No field in any port uses manual registration in T: every checked field
points to U memory. The two places where a T object would have to be
registered are memcached/hash with the hash table in U, and the OpenSSL
`ex_data` pair (I6).

Two fields have no metadata source even in principle with the current
registry, because the object is static data in U: `poptStrerror` and libzip's
empty entry name (I12).
