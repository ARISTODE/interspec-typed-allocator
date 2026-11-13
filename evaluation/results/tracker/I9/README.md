# I9 raw output: memcached/hash port (hash call only)

Tracker item I9 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
VM. Nothing here is a timing measurement; `elapsed_ns` in the bench output is
not used.

## What the artifact has for this boundary

The artifact isolates one function at the memcached/hash boundary:
`hash_untrusted(data, len)`, which returns XXH3 of the key
(`code/generated_wrappers/samples/memcached_hash_bridge_wasm/`). memcached's
hash table (`assoc.c`) runs in T in the artifact's memcached build
(`code/rlbox_split_benchmarks/memcached_hash/`), with in-process checks on item
pointers. The call takes one pointer and returns a number. So at the boundary
that actually runs isolated:

- SP2 has a field: the key, which U reads and never writes.
- **SP1 has no field**: U reads everything it is handed.
- **SP3 has no field**: U returns no pointer to T. There is no registry.

The four SP3 fields in the paper's coverage row for memcached/hash
(`assoc_find`, `assoc_iterate`, the lock handle, the thread name) come from the
static analysis with `assoc.c` counted as untrusted, which is a different cut
from the one that runs. The item's condition asks for three switches; this
port can show one. The item stays blocked on JH's decision between this port
and a new one that moves the hash table into U.

| Directory | Commit | Result |
|---|---|---|
| `01-tests-before-implementation-71cec99/` | `71cec99` | The port and its test exist; the wrapper copies the key back. The "on" case of SP2 fails, as intended. Benign 18/18. |
| `02-implementation-68e7ece/` | `68e7ece` | The SP2 test passes; benign 18/18. |

Each run is the unmodified output of `scripts/run_hash_port.sh`, started once
from a clean checkout. `sp1_no_field` and `sp3_no_field` record that turning
those switches off changes nothing; they are not switch tests.

| Policy | Field | Switch off | Switch on |
|---|---|---|---|
| SP2 | the key | U flips byte 0 of its copy; T's key then starts with `0x94` | T's key still starts with `0x6b` |

## Benign run (`benign/`)

Key spaces of 1, 100 and 10,000 keys with 1 to 100,000 hash operations, three
programs each (native, RLBox-only, InterSpec): 18 processes. The keys and the
generator are those of the artifact's microbenchmark with one client. Every
isolated variant prints the same XOR of the hash values as the native build.
The hash function and `xxhash.h` are those of memcached at the revision pinned
in `evaluation/coverage/pins.json`.
