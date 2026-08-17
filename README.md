# InterSpec Typed Allocator

Minimal proof-of-concept for extending InterSpec SP3 with trusted allocation metadata.

The PoC uses RLBox with the NaCl SFI backend. U may freely corrupt object bytes, while T keeps authoritative allocation metadata `{base, size, type_hash}` and validates U-controlled pointers before trusted use.

## Design principles

• Keep the implementation small and readable.
• Reuse RLBox and NaCl mechanisms instead of rebuilding them.
• Separate allocation metadata from untrusted object contents.
• Make each PoC check independently testable.
• Prefer a simple end-to-end build over premature generality.

## First milestone

The initial PoC will demonstrate:

• correct typed pointer → pass
• wrong allocated type → reject
• out-of-bounds access → reject
• freed pointer → reject
• untracked pointer → reject
• valid interior pointer → pass
• interior pointer crossing the allocation end → reject

Automatic Uriah type inference and InterSpec policy inference are intentionally deferred until the runtime PoC is stable.
