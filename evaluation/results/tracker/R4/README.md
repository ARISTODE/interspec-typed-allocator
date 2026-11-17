# R4: the two worst harness rows inside a complete operation

Tracker item R4 in `EVAL_TRACKER.md`. Machine as in `../P1/`; times in PT.

The memcached hash table no longer shows a cost after R1 (-3.0%,
`../R1/README.md`), so this item is about zip/libzip.

`01-vm-00a20ec/` (2026-11-17, driver `after.sh`, steps `r4/*`): a second
workload of the zip/libzip port, added in `00a20ec`. One iteration opens an
archive with 1,000 entries (`evaluation/parity/zip_listing/tree-1000.zip`),
queries size and names of every entry, and closes the archive.

| Step | Content |
|---|---|
| `build/` | build and checks of the port at `00a20ec` |
| `p7-listing/` | three variants and tracked-no-check, P7 protocol |
| `p6-listing/` | per-policy configurations |
| `instr-listing/`, `instr-query/` | instructions per listing and per query (each count made twice, all repeats equal) |

## Result: the listing costs more than the query loop, not less

| Variant | Time per listing | Against RLBox-only | Instructions per listing |
|---|---:|---:|---:|
| native | 1,456 us | +173.6% (+155.4 to +191.7) | 8,040,955 |
| RLBox-only | 534 us | | 6,498,335 |
| tracked-no-check | 757 us | +38.9% (+31.0 to +57.1) | 7,984,378 (+22.9%) |
| InterSpec | 887 us | +62.9% (+52.4 to +73.1) | 8,290,703 (+27.6%) |

Per-policy protocol on the same binaries: all on against RLBox-only +62.6%
(+53.1 to +75.1); all off against RLBox-only +42.9% (+32.9 to +50.8); SP3 alone
against all off +17.1% (+9.7 to +26.6).

Where the cost comes from (profiles in `instr-listing/run/callgrind-profiles.tar.gz`):

- libzip allocates the name of every entry when it opens the archive. These
  1,000 allocations per listing come from an allocation site whose objects
  cross the boundary, so each is recorded in the registry and removed again at
  close: 1,000 `allocate_with_hash_unlocked` and 1,000 `release_unlocked` calls
  per listing. Of the 1,552,000 additional instructions of the all-off
  configuration, about 1,450,000 are this bookkeeping: the registry's own
  functions (449,000), red-black tree insertion and removal (358,000) and the
  host's `malloc` and `free` for the tree nodes (about 640,000; 3 calls of each
  per recorded allocation).
- The 2,000 checks of a listing add 239,000 instructions (120 per check) and
  130 us (65 ns per check). In the query loop a check costs about 12 ns; here
  every check looks up a different one of 1,000 records in a tree.

So the query loop of the paper's table (+20.0%) is not the worst case of this
boundary. An operation that allocates many objects of a recorded site is
worse, and this is a cost of the registry's bookkeeping, which R1 did not
change ("the `std::map` of allocations is unchanged").

## A flaw of this workload: the native column

The native program opens the archive from the file in every iteration; the
sandboxed programs open it from a buffer that was read once. The native time
therefore contains file I/O that the others do not have (native is 2.7 times
slower than RLBox-only). The comparison between the sandboxed variants is not
affected. To be corrected before the workload is used in the paper.

`instr-query/`: the query loop built at `00a20ec` executes 1,339.4 (RLBox-only)
and 1,557.3 (InterSpec, +16.3%) instructions per query; the campaign's
binaries at `930cb20` gave 1,328.4 and 1,568.3 (+18.1%). The harness changed
between the two commits (the query is now a function shared with the listing).
