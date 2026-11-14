# I9 raw output: memcached/hash

Tracker item I9 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
VM. Nothing here is a timing measurement; `elapsed_ns` in the bench output is
not used.

Two cuts of this boundary are built and tested by `scripts/run_hash_port.sh`:

1. **The hash table in U** (JH decision of 2026-11-14): memcached's hash
   function and its hash table run in the sandbox, T keeps the items. SP1, SP2
   and SP3 each have a field. This is the cut the tracker item is about. It is
   not in the artifact. Steps `assoc-*`.
2. **The hash call only**, as the artifact isolates it: SP2 is the only policy
   with a field. Kept as a fallback. Steps `switch-tests` and `benign`.

| Directory | Commit | Result |
|---|---|---|
| `01-tests-before-implementation-71cec99/` | `71cec99` | Hash call only: the wrapper copies the key back; the "on" case of SP2 fails, as intended. Benign 18/18. |
| `02-implementation-68e7ece/` | `68e7ece` | Hash call only: the SP2 test passes; benign 18/18. |
| `03-assoc-tests-before-policies-83f3266/` | `83f3266` | Hash table in U, before the policies: the wrapper copies the whole item in, copies U's version back and resolves handles through a table in T with slot reuse. The SP1, SP2 and SP3 tests, the handle cases that need the registry and the benign cases that count checks fail, as intended (benign 10/15). The handle cases on the build without any InterSpec check pass. |
| `04-assoc-policies-d7cc3f5/` | `d7cc3f5` | Hash table in U with the three policies: all tests pass; benign 15/15. Both runs also repeat the hash-call steps, which pass. |

Each run is the unmodified output of the script, started once from a clean
checkout. Scratch builds preceded the commits and are not evidence; in them
one compile error was fixed and two tests were corrected before the
implementation commit (`83f3266`: the SP2 pair now runs with SP1 off in both
cases, so that it differs in SP2 only, and the smallest benign case got enough
operations to hand T at least one item).

## The hash table in U

`assoc_u.c` follows memcached's `assoc.c` at the pinned revision (the same
bucket array and chaining, `assoc_find`, `assoc_insert`, `assoc_delete`, the
iterator). Inside the sandbox it cannot read T's items, so an entry is U's
copy of the item (`assoc_bridge.h`) and carries a handle that names T's item.
The table has a fixed size and takes no locks: there is no expansion thread
and the port is single-threaded. The trusted program is a cache workload
(get, set, delete with a fixed seed, then a walk over the table), not the
memcached server.

| Policy | Field | Switch off | Switch on |
|---|---|---|---|
| SP1 | of an item, everything but `nkey` and the key: the other header fields (three are T pointers) and the value | U receives the whole item: `exptime=0x5ec2e701`, 18 value bytes starting `545f5345` ("T_SE") | U receives `exptime=0x0`, no value bytes |
| SP2 | the item fields other than the chain link, and the keys passed to find and delete | U sets the reference count to `0xffff` and flips the key's first byte in its copy; T's item then has `refcount=65535` and a key starting `0x94` | T's item still has `refcount=1` and a key starting `0x6b` |
| SP3 | the item handle that `assoc_find` and `assoc_iterate` hand back | U returns the handle of an item T has freed; T's handle table has reused the slot, and T is handed the item of `k1` for key `k0` | `INTERSPEC_REJECT boundary=memcached_hash operation=assoc_find reason=untracked`, exit status 86 |

How the handle works. Without SP3 the handle is a slot of a table in T, and a
freed slot is reused, as a wrapper without InterSpec would keep it. (RLBox's
own application-pointer table cannot be used here: it holds at most about
4,000 entries.) With SP3 on, T registers each item before its handle reaches
U (manual registration in T), the handle is the registration token, which is
never issued twice, and what U hands back must be the token of a live
registered item of the item type.

Handle cases (`assoc-switch-tests/handle_*` with all policies on,
`assoc-handles-rlbox-only/` on a test build without any InterSpec check):

| Case | What U returns | RLBox-only | InterSpec, SP3 on |
|---|---|---|---|
| legitimate | the handle of the item | T gets `k0` | the same |
| never issued | `0x5ec2e7f0` | rejected (`unknown_handle`) | rejected (`untracked`) |
| freed item | the handle of an item T freed, after T inserted another | **accepted**: T is handed `k1` for `k0` | rejected (`untracked`) |
| other live item | the handle of another item in the table | accepted: T is handed `k1` for `k0` | **accepted as well** |

The last row is the stated limit of SP3: it cannot tell two live objects of
the same type apart. Here T could compare the key of the item it is handed
with the key it asked for; that is an application check, not SP3.

Benign run (`assoc-benign/`): key spaces of 4, 1,000 and 20,000 keys with 40
to 100,000 operations, three programs each: 15 processes. Every isolated
variant prints the same counts of gets, hits, sets and deletes, the same
checksum of the values read, and the same result of the final walk as the
native build of the same code.

## The hash call only

### What the artifact has for this boundary

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
from the one that runs. With this cut alone the item's condition (three switches) cannot hold, which
is why JH decided to move the hash table into U.

Each run is the unmodified output of `scripts/run_hash_port.sh`, started once
from a clean checkout. `sp1_no_field` and `sp3_no_field` record that turning
those switches off changes nothing; they are not switch tests.

| Policy | Field | Switch off | Switch on |
|---|---|---|---|
| SP2 | the key | U flips byte 0 of its copy; T's key then starts with `0x94` | T's key still starts with `0x6b` |

### Benign run (`benign/`)

Key spaces of 1, 100 and 10,000 keys with 1 to 100,000 hash operations, three
programs each (native, RLBox-only, InterSpec): 18 processes. The keys and the
generator are those of the artifact's microbenchmark with one client. Every
isolated variant prints the same XOR of the hash values as the native build.
The hash function and `xxhash.h` are those of memcached at the revision pinned
in `evaluation/coverage/pins.json`.
