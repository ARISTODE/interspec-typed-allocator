# C3: metadata sources for full SP3

Tracker item C3 in `EVAL_TRACKER.md`.

`02-table-after-I9-I10/` is the output of

    python3 tools/render_sp3_metadata_table.py \
      --artifact-reports <interspec-artifact>/data/raw/policy_reports \
      --records evaluation/coverage/sp3_metadata_sources.json \
      --out evaluation/results/tracker/C3/02-table-after-I9-I10

`SP3_METADATA_SOURCES.md` there is the table; the CSV has the same rows. The
script refuses to run if a case in the artifact's files has no record or a
record names a case that does not exist. `01-table/` is the table before the
hash table of memcached was moved into U (I9) and the `ex_data` pair was added
to the TLS bridge (I10); it is kept for the record.

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
  unknown. Nothing in the artifact says which 16 rows are meant. The isolated
  TLS bridge of the artifact has no pointer crossing; the table lists the one
  field the port adds, the object stored with `SSL_set_ex_data` (I6).

So the table gives expected domain, type source and bounds source for 31
fields: the 24 the artifact identifies and 7 that only the ports have. 20 are
checked by a port. Of the 11 that are not, 2 are memcached/hash calls outside
both cuts of that boundary (lock table, thread naming), 3 do not cross the
boundary in the port's wrapper design, and 6 belong to calls a port does not
make or does not isolate.

Three fields use manual registration in T, because they point to T objects
whose handle U stores and returns: the item returned by `assoc_find`, the item
yielded by `assoc_iterate` (memcached/hash with the hash table in U), and the
connection returned by `SSL_get_ex_data`. The other 17 point to U memory and
are typed at an allocation site or a declared helper.

Two fields have no metadata source even in principle with the current
registry, because the object is static data in U: `poptStrerror` and libzip's
empty entry name (I12).
