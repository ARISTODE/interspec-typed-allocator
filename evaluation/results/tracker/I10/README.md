# I10 and I6 raw output: nginx/openssl TLS bridge port with the ex_data pair

Tracker items I10 and I6 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
VM. Nothing here is a timing measurement; `elapsed_ns` in the bench output is
not used.

## What the artifact has for this boundary

The artifact's isolated build of this boundary is a standalone TLS bridge
(`code/generated_wrappers/samples/nginx_openssl_phase1_bridge_wasm/`): the
OpenSSL state of a TLS server lives in the sandbox, and the trusted side
exchanges copied buffers and numeric handles with it. Its own README says
that the bridge is not yet wired into nginx's connection path. Its ABI header
says that no `SSL*`, `SSL_CTX*`, `BIO*` or `X509*` pointer may cross the
boundary. Two consequences for this item:

- The port covers that standalone bridge, not nginx. The trusted program
  (`tls_app_bench.cpp`) is modelled on the artifact's smoke tests: a TLS 1.3
  handshake and request and response rounds between the sandboxed server state
  and an ordinary OpenSSL client in the same process, through memory BIOs.
- The bridge itself has no SP3 field: U returns no pointer to T. JH decided on
  2026-11-14 to add the `ex_data` pair that nginx uses, which gives SP3 a
  pointer of T to check (see "The ex_data pair" below). The SP3 rows of the
  paper's coverage table for nginx/openssl (5 fields and 11 unknown) describe
  the OpenSSL API as nginx calls it natively, not this bridge.

OpenSSL is 1.1.1w (`e04bd34`), the version the artifact's build script names
for the isolated module, with that script's options. The coverage database for
this boundary (C1) was built from OpenSSL 3.5.9, because no version was
recorded for the analysis; the two differ.

| Directory | Commit | Result |
|---|---|---|
| `01-tests-before-implementation-3fc08fc/` | `3fc08fc` | The port and its tests exist; the wrapper copies T's output buffers and out-parameters in and copies inputs back. The "on" cases of SP1 and SP2 fail, as intended. Benign 18/18. |
| `02-implementation-e0daf9c/` | `e0daf9c` | Switch tests pass; benign 18/18. |
| `03-ex-data-tests-before-check-92a2e79/` | `92a2e79` | The ex_data pair and its tests exist; T uses the object behind the returned handle without a registry check. The SP3 test and the wrong-type case fail, as intended, and the benign runs of the InterSpec variant fail because no check is counted (12/18). The same cases on the RLBox-only test build pass with RLBox's expected behavior. |
| `04-ex-data-check-7d718e6/` | `7d718e6` | T registers its objects and checks the returned one. All tests pass; benign 18/18. |

Each run is the unmodified output of `scripts/run_tls_port.sh`, started once
from a clean checkout. Before the two commits, scratch builds were needed to
get the module to link, and they are not evidence. Three things were added
around the unchanged shim: stubs for `getuid` and its relatives (WASI has no
user ids), a stub for `ossl_debug_ssl_ctx_new_stage` (a diagnostic function of
the artifact authors' locally patched OpenSSL, which the artifact does not
ship), and a fix to the shared engine so that a boundary without a registry
compiles.

## Policies at this boundary

| Policy | Field | Switch off | Switch on |
|---|---|---|---|
| SP1 | the output buffers of `read_plain` and `drain_encrypted` and the count out-parameters, which U writes and never reads | U is handed T's buffer contents: before its first read it sees `T_STALE_` (`545f5354414c455f`), older data of T | T's contents are not copied in; U sees what its own staging memory held (here a TLS record it produced earlier) |
| SP2 | the ciphertext passed to `feed_encrypted` and the plaintext passed to `write_plain`, which U reads and never writes | U flips byte 0 of its copy of the plaintext; T's response buffer then starts with `0xb9` | T's response buffer still starts with `0x46` |
| SP3 | the value `SSL_get_ex_data` returns, which stands for T's connection object | U returns the handle of T's server configuration; T uses that object as a connection and writes to it (`conf_limit` 1000 becomes 1001) | `INTERSPEC_REJECT boundary=nginx_openssl operation=ex_data reason=wrong_type`, exit status 86 |

## The ex_data pair (I6)

nginx attaches its connection object to an `SSL` with `SSL_set_ex_data` and
its server configuration to an `SSL_CTX` with `SSL_CTX_set_ex_data`, and later
asks OpenSSL for the connection with `SSL_get_ex_data`. `tls_exdata.c` adds
these three real OpenSSL calls next to the artifact's shim (which it includes
unchanged, to reach the shim's private table of connections). In every round
the trusted program asks for its connection and counts the request on it.

A pointer is 32 bits wide inside the sandbox, so T cannot store an address.
In every build T stores an RLBox application-pointer handle
(`get_app_pointer`) and resolves the returned value with RLBox's table
(`lookup_app_ptr`), which knows only handles that T issued and records no
type. With InterSpec, T also registers each object with its type before the
handle reaches U (manual registration in T), and with SP3 on the object
behind the returned handle must be a live registered object of T of the
connection type.

Four cases, each on the InterSpec test build with all policies on
(`switch-tests/ex_data_*`) and on a test build without any InterSpec check
(`ex-data-rlbox-only/`):

| Case | What U returns | RLBox-only | InterSpec, SP3 on |
|---|---|---|---|
| legitimate | the stored handle | accepted, request counted on the connection | the same, one check |
| never issued | `0x5ec2e7f0` | rejected by RLBox's handle table (`unknown_handle`) | rejected the same way |
| wrong type | the handle of T's server configuration | **accepted**: T writes to the configuration as if it were a connection (`conf_limit=1001`) | rejected, `wrong_type` |
| other connection | the handle of another live connection | accepted: the request is counted on the wrong connection (`other_requests=1`) | **accepted as well** |

The last row is a limit, not a pass: a pointer to another live object of the
same type passes SP3 unless T says which object it expects. The earlier
domain-only form of SP3 is not run; JH discarded it on 2026-11-13 (D1).

## Benign run (`benign/`)

Four request and response sizes (64/256, 512/4096, 100/65536, 20000/1) with
one to eight rounds, three programs each (native, RLBox-only, InterSpec): 18
processes. Since `7d718e6` each round also asks for the connection through
`ex_data`, and the number of requests counted on it is a result field. Keys and nonces are random, so ciphertext is not compared. Every
isolated variant negotiates the same protocol version and cipher as the native
build (TLS 1.3, `TLS_AES_256_GCM_SHA384`) and both sides receive the same
plaintext, by hash.
