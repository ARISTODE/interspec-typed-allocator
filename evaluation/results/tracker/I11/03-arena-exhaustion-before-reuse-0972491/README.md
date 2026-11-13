# Arena exhaustion in the ucl/libucl port before buffer reuse

Not a pass or fail run of I11: a record of a limit of the typed allocator.

The binaries were built from commit `0972491`, where the U shim allocates
three registered objects per parse and releases them afterwards. Each program
ran once on `evaluation/parity/ucl/nested.conf` with the lookups `server.name`
and `logging.level` for 10,000, 20,000, 30,000 and 200,000 parses
(`steps.txt`, one stdout and one stderr file per run).

RLBox-only completes every run. Both variants with the registry (tracking
without check, InterSpec) complete 20,000 parses and fail at 30,000 and at
200,000 with `ucl benchmark error: ucl_parse`: the 4 MiB arena hands out each
address once and does not reuse released ones (`allocate_with_hash_unlocked`
in `include/interspec/runtime.h`), so it is exhausted and the next allocation
returns 0.

The fix in the port is in the next directory: the shim keeps one buffer per
result and reuses it. The allocator itself is unchanged.
