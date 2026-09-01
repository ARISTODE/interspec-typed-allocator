# RLBox wasm2c backend support

P9b uses RLBox's wasm2c sandbox as the paper-compatible execution backend for Extended SP3.

The backend patch is intentionally small. It pins the upstream RLBox and WABT revisions used by the build, extends the wasm2c `env` import context with opaque InterSpec dispatch callbacks, and exposes two trusted helpers from the RLBox backend implementation:

1. `reserve_typed_arena(size)` reserves one ordinary Wasm allocation that T suballocates with trusted metadata.
2. `sandbox_address(ptr)` converts a host view of a Wasm pointer back to its 32-bit linear-memory offset.
3. `set_interspec_runtime(...)` installs host-only dispatch functions used by generated direct Wasm imports.

Allocation-site provenance does not use a mutable SiteId argument from U. Each analyzed source allocation is rewritten to a unique direct Wasm import. wasm2c turns that fixed import into a distinct trusted host wrapper, and the wrapper embeds the SiteId before dispatching to T.

Run `apply_backend.py --root <rlbox_wasm2c_sandbox checkout>` only on the exact revision listed in `manifest.json`. The script also replaces the upstream moving `main` dependency pins for RLBox and WABT with the manifest revisions.
