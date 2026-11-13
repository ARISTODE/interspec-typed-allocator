# I10 raw output: nginx/openssl TLS bridge port

Tracker item I10 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
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
- **There is no SP3 field.** U returns no pointer to T, so there is nothing for
  the object registry to check and the port has no registry. The item's
  condition asks for three switches; only two have a field here. The SP3 rows
  of the paper's coverage table for nginx/openssl (5 fields and 11 unknown)
  describe the OpenSSL API as nginx calls it natively, not this bridge.

OpenSSL is 1.1.1w (`e04bd34`), the version the artifact's build script names
for the isolated module, with that script's options. The coverage database for
this boundary (C1) was built from OpenSSL 3.5.9, because no version was
recorded for the analysis; the two differ.

| Directory | Commit | Result |
|---|---|---|
| `01-tests-before-implementation-3fc08fc/` | `3fc08fc` | The port and its tests exist; the wrapper copies T's output buffers and out-parameters in and copies inputs back. The "on" cases of SP1 and SP2 fail, as intended. Benign 18/18. |
| `02-implementation-e0daf9c/` | `e0daf9c` | Switch tests pass; benign 18/18. |

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
| SP3 | none | same behavior as on (`sp3_no_field`) | |

## Benign run (`benign/`)

Four request and response sizes (64/256, 512/4096, 100/65536, 20000/1) with
one to eight rounds, three programs each (native, RLBox-only, InterSpec): 18
processes. Keys and nonces are random, so ciphertext is not compared. Every
isolated variant negotiates the same protocol version and cipher as the native
build (TLS 1.3, `TLS_AES_256_GCM_SHA384`) and both sides receive the same
plaintext, by hash.
