# I7 raw output: ffmpeg/libvpx registry port

Tracker item I7 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
VM. Nothing here is a timing measurement; `elapsed_ns` in the bench output is
not used.

libvpx 1.15.2 (`d168454`, pinned in `evaluation/coverage/pins.json`) runs
inside an RLBox wasm2c sandbox behind the shim, the ABI header and the
`setjmp.h` stub of the `interspec-artifact` wrapper
(`integration/ffmpeg_libvpx/untrusted/`, `shared/`), all three unchanged, with
the artifact's libvpx configuration (C-only target, one thread, VP8 and VP9).

## What the trusted side is, and what it is not

The artifact's workload is FFmpeg transcoding through libvpx. The artifact
ships neither a patched FFmpeg nor its inputs, and its trusted bridge (2,052
lines) carries its own handle tables and profiling. The port does not use
FFmpeg. Its trusted program is a libvpx client (`vpx_app_bench.cpp`) that makes
the calls an application such as FFmpeg makes: `encode`, `get_cx_data`,
`decode`, `get_frame`. It encodes synthetic I420 frames with VP8 and decodes
the resulting packets again. Only VP8 is exercised and only VP8's buffers are
registered; VP9 is compiled in, because the shim refers to it, and is not
covered.

| Directory | Commit | Result |
|---|---|---|
| `01-tests-before-implementation-15b4d52/` | `15b4d52` | The port and its tests exist; the wrapper copies T's values of the unused image fields in and copies planes and compressed data back. The "on" cases of SP1 and SP2 fail, as intended. The SP3 test already passes, because the registry check and its switch are in the shared engine (tested red then green under I11). Benign 28/28. |
| `02-implementation-aa6a274/` | `aa6a274` | Switch tests pass; benign 28/28. |

Each run is the unmodified output of `scripts/run_vpx_port.sh`, started once
from a clean checkout. Before the two commits, scratch builds were needed to
get libvpx configured for WASI (the linker driver has to be set, PIC has to be
off) and one compile error in the trusted program was fixed. Those builds were
not kept and are not evidence.

## Policies at this boundary

| Policy | Field | Switch off | Switch on |
|---|---|---|---|
| SP1 | five fields of the image passed to `encode` that the encoder does not use: `user_priv`, `img_data`, `fb_priv` (T pointers), `img_data_owner`, `self_allocd` | U is handed T's values (`user_priv=0x5ec2e701 img_data=<T pointer> fb_priv=0x5ec2e703 img_data_owner=1`) | U is handed 0 |
| SP2 | the raw planes passed to `encode` and the compressed data passed to `decode`, which U reads and never writes | U flips luma byte 0 of its copy; T's frame then starts with `0xef` | T's frame still starts with `0x10` |
| SP3 | the packet buffer returned by `get_cx_data` and the three planes returned by `get_frame` | U returns an untracked heap copy of the luma plane; T accepts it | `INTERSPEC_REJECT boundary=ffmpeg_libvpx operation=frame_plane reason=untracked`, exit status 86 |

With SP3 on, three more wrong pointers are rejected (`sp3_other_faults`): a
live object of another type (`wrong_type`), a released object (`untracked`),
and a live frame buffer that is smaller than the plane (`out_of_bounds`).

The registry learns the buffers at their allocation sites in libvpx. The build
patches two files by exact text replacement and links the patched copies ahead
of `libvpx.a` (`scripts/build_vpx_port.sh`): the VP8 frame buffers in
`vpx_scale/generic/yv12config.c` and the encoder's output buffer in
`vp8/vp8_cx_iface.c`. The planes T receives are pointers into a frame buffer,
not to its start; the check accepts an interior pointer and bounds the read by
what remains of the object. The RLBox-only module uses the unmodified library.

## Benign run (`benign/`)

Four frame sizes (64x48, 176x144, 352x288, 130x98) with one to twelve frames,
four programs each: 28 processes. Every isolated variant prints the same
packet count, encoded size, hash of the encoded bytes, frame count and hash of
the decoded planes as the native build of the same libvpx revision with the
same C-only target.
