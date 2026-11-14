# I12 raw output: zip/libzip registry port

Tracker item I12 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
VM. Nothing here is a timing measurement; `elapsed_ns` in the bench output is
not used.

libzip 1.11.4 (`6f8a0cd`) and zlib 1.3.2 (`da607da`), both pinned in
`evaluation/coverage/pins.json`, run inside an RLBox wasm2c sandbox. From the
`interspec-artifact` wrapper the port takes the shim (`zip_shim.c`, unchanged),
the two configuration headers and the list of source files; the artifact does
not ship libzip or zlib. The trusted interface is the shim call,
`stat_and_get_names(idx, &size, &name_direct, &name_stat)`, on an archive
opened read-only from a buffer.

| Directory | Commit | Result |
|---|---|---|
| `01-tests-before-implementation-9c6e08f/` | `9c6e08f` | The port and its tests exist; the wrapper copies T's out-parameter values in, copies the archive back and always checks the returned names. The "on" cases of SP1 and SP2 and the "off" case of SP3 fail, as intended. Benign 40/40. |
| `02-implementation-0082565/` | `0082565` | Switch tests pass; benign 40/40. |

Each run is the unmodified output of `scripts/run_zip_port.sh`, started once
from a clean checkout. Before the two commits were made, the port was built
three times in a scratch directory to get it working. Two things had to be
fixed, and neither is evidence: WASI libc has no `chmod` (a stub was added;
the call is in code that writes archives to disk, which the port never does),
and 64-bit arguments have to be declared `long long`, because RLBox maps
`long` to the 32-bit type inside the sandbox.

## Policies at this boundary

| Policy | Field | Switch off | Switch on |
|---|---|---|---|
| SP1 | the three out-parameters, which U writes and never reads | U is handed T's values `0x5ec2e70100000001`, `0x5ec2e702`, `0x5ec2e703` | U is handed 0 |
| SP2 | the archive bytes, which U reads and never writes | U flips byte 0 of its copy; T's archive then starts with `0xaf` | T's archive still starts with `0x50` |
| SP3 | the two entry-name pointers that U returns | U returns an untracked heap copy; T accepts it | `INTERSPEC_REJECT boundary=zip_libzip operation=name_direct reason=untracked`, exit status 86 |

With SP3 on, three more wrong pointers are rejected (`sp3_other_faults`): a
live object of another type (`wrong_type`), a released object (`untracked`),
and a live object of the right type that holds the name without its terminator
(`out_of_bounds`; T looks for the terminator only inside the object).

Unlike the ucl/libucl port, the registry learns the name buffers at libzip's
own allocation site: the build instruments the `malloc` in `_zip_string_new`
(`policy.json`), routes the buffer for a converted name in `zip_utf-8.c` to a
declared site, and releases both in `_zip_string_free`. The library is
otherwise unmodified, and the RLBox-only module uses the unmodified sources.

## A limit of the registry check (`limit_static_empty_name`)

For an entry without a name (`filename_empty.zip`) libzip returns a pointer to
a static empty string. Static data is not a registered object, so with SP3 on
T rejects this legitimate archive (`reason=untracked`, exit status 86); with
SP3 off the run completes. The two cases record this behavior; they are not
a pass criterion for the port. The archive is not part of the benign set.

## Benign run (`benign/`)

Five archives from libzip's `regress/` directory (`evaluation/parity/zip/`),
each with one iteration and with enough iterations to read every entry twice,
four programs each: 40 processes. `test-cp437.zip` has 16 names that libzip
converts to UTF-8. Every isolated variant prints the same entry count,
checksum, last name and last size as the native build of the same sources.
