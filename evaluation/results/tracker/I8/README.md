# I8 raw output: magick/libpng registry port

Tracker item I8 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
VM. Nothing here is a timing measurement; `elapsed_ns` in the bench output is
not used.

libpng 1.6.59 (`cd952f4`) and zlib 1.3.2 (`da607da`), both pinned in
`evaluation/coverage/pins.json`, run inside an RLBox wasm2c sandbox. From the
`interspec-artifact` wrapper the port takes the shim, the configuration header
and the list of source files; the artifact does not ship libpng or zlib. The
trusted interface is that of the artifact wrapper:
`decode_rgba(png, png_len, &w, &h, &rgba, &rgba_len)` and
`encode_rgba(rgba, w, h, &png, &png_len)`. As in the artifact, the workload is
libpng alone; ImageMagick is not part of it.

| Directory | Commit | Result |
|---|---|---|
| `01-tests-before-implementation-38800f3/` | `38800f3` | The port and its tests exist; the wrapper copies T's out-parameter values in and copies both inputs back. The "on" cases of SP1 and SP2 fail, as intended. The SP3 test already passes, because the registry check and its switch are in the shared engine (`include/interspec/boundary/wasm_port.h`, tested red then green under I11). Benign 48/48. |
| `02-implementation-dc8abb9/` | `dc8abb9` | Switch tests pass; benign 48/48. |
| `03-allocator-reuse-9f803c0/` | `9f803c0` | After the allocator change and with the shim back to one allocation per call: switch tests pass, benign 48/48, 50,000 rounds complete. |

Each run is the unmodified output of `scripts/run_png_port.sh`, started once
from a clean checkout. One scratch build preceded the two commits; it was not
kept and is not evidence.

## Policies at this boundary

| Policy | Field | Switch off | Switch on |
|---|---|---|---|
| SP1 | the out-parameters of decode and encode, which U writes and never reads | U is handed T's values (`w_in=0x5ec2e701 h_in=0x5ec2e702 rgba_in=<T pointer> size_in=0x5ec2e703`) | U is handed 0 |
| SP2 | the PNG bytes and the pixels to encode, which U reads and never writes | U flips byte 0 of its copy of the PNG; T's copy then starts with `0x76` | T's copy still starts with `0x89` |
| SP3 | the decoded pixels and the encoded image that U returns | U returns an untracked heap copy of the pixels; T accepts it | `INTERSPEC_REJECT boundary=magick_libpng operation=decoded_pixels reason=untracked`, exit status 86 |

With SP3 on, three more wrong pointers are rejected (`sp3_other_faults`): a
live object of another type (`wrong_type`), a released object (`untracked`),
and a live object of the right type that is smaller than the size U reports
(`out_of_bounds`).

## Change to the artifact shim

The artifact shim allocates the decoded pixels and the encoded image with
`malloc`/`realloc` and frees them when T is done. The port's shim does the
same through three small functions (`returned_alloc`, `returned_grow`,
`returned_free` in `magick_png_shim.c`; every changed line is marked `port:`),
which in the tracked builds allocate at declared sites that the registry
knows. Nothing else differs from the artifact shim.

History: the commits `38800f3` and `dc8abb9` kept one buffer of each kind and
reused it, because the typed allocator then never reused a released address.
After the allocator change of 2026-11-14 (`evaluation/results/tracker/A1/`)
the shim went back to one allocation per call (`9f803c0`).
`03-allocator-reuse-9f803c0/` is the rerun from a clean checkout: switch tests
pass, benign 48/48, and 50,000 decode and encode rounds complete in all three
isolated variants (`long-run-*`).

## Benign run (`benign/`)

Six PngSuite images from libpng's `contrib/pngsuite/`
(`evaluation/parity/png/`): 1-bit gray, 8-bit RGB, 8-bit palette, 16-bit gray
with alpha, 8-bit RGBA, and a palette image with transparency. Each is decoded
to RGBA and encoded again, once and twice, by four programs: 48 processes.
Every isolated variant prints the same dimensions, pixel hash, encoded size
and encoded hash as the native build of the same sources.
