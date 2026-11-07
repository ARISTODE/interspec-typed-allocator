# Extended SP3 security-delta results

**Status: partial verified observations; remaining full integration experiments pending.**

## First independently verified observations

The H1 YAML job completed in GitHub Actions run
[`42423558556`](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42423558556).
Its [unaltered raw artifact](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42423558556/artifacts/13594930930)
contains 15 executions, a SHA-checked manifest and an independently generated
report. The verifier marked the evidence integrity as `verified`.

| H1 YAML fault | RLBox-only versus legitimate | T sanitizer | Extended SP3 |
| --- | --- | --- | --- |
| 1, wrong type | Same T-visible YAML result | None | Rejected `wrong_type` |
| 2, untracked | Same T-visible YAML result | None | Rejected `untracked` |
| 3, stale allocation | Different output hash; **inconclusive** | None | Rejected `untracked` |
| 4, excessive extent | Different output length/hash; **inconclusive** | None | Rejected `out_of_bounds` |
| 5, same-type substitution | Same T-visible YAML result | None | Accepted |

Mode 4 is particularly relevant to the preregistration: the RLBox-only
driver processed 8,193 bytes for the injected scalar even though the U
staging object's expected capacity is 8,192 bytes. Its existing bridge
checks the sandbox's remaining memory, not a fixed T scalar-length cap.
This contradicts the plan's premise that all evaluated bridges enforce a
T-specific capacity bound. No sanitizer error was observed in that case,
and the difference alone does not establish security harm beyond arbitrary
U-chosen content. The preregistered prediction has **not** been rewritten.

H1 memcached/nginx/rsync and H2 memcached/libyaml are still being collected
or repaired. Do not treat this partial YAML result as a global H1 conclusion.

## Experiment matrix and outstanding work

The preregistered hypotheses and predicted results are in
[`docs/SP3_SECURITY_DELTA_PLAN.md`](docs/SP3_SECURITY_DELTA_PLAN.md).
They are not observations. The earlier 50/50 memcached gate is a starting
correctness baseline, not a substitute for the new fault experiments.

The dedicated GitHub Actions workflow `sp3-security-delta` builds the H1 and
H2 comparators, collects raw outcomes, reruns the 50-case correctness gate
after each memcached scenario, independently checks recorded hashes, and
writes a generated results report into each evidence artifact. Its fault and
sanitizer binaries must never contribute to performance numbers.

| Question | Boundary | Comparator |
| --- | --- | --- |
| H1, U-domain | memcached/bipbuffer | Fault-only RLBox versus Extended SP3, with matched-content control |
| H1, U-domain | rsync/popt | Fault-only RLBox versus Extended SP3 |
| H1, U-domain | nginx/libpcre8 | Fault-only RLBox versus Extended SP3 |
| H1, U-domain | yaml/libyaml | Fault-only RLBox versus Extended SP3 |
| H2, T-domain | memcached LRU | Upstream raw, domain-only, T-registered Extended SP3, one-use handle |
| H2, T-domain | libyaml read-handler | Real API with project-authored T-side corruption, domain-only versus Extended SP3 |

The libyaml driver uses `yaml_parser_set_input` and RLBox domain checks, but
the mutation is in project-authored T code. It is not evidence of an upstream
libyaml exploit or wasm2c malicious return path. The nginx/OpenSSL
`ex_data_ptr` case remains outside this implementation; this repository has
no corresponding wasm2c integration.

A rejection alone is not evidence of T harm prevented. Address-only tracking
cannot distinguish address reuse (ABA) without a token or another temporal
identity mechanism. Matching type/domain does not prove intended-object
identity without an authenticated expected base. Same-type substitution is a
documented limitation.

The partial observations do not establish either hypothesis across all
boundaries. See [`docs/SP3_SECURITY_DELTA_IMPLEMENTATION.md`](docs/SP3_SECURITY_DELTA_IMPLEMENTATION.md)
for reproduction commands and limits. Do not update manuscript guarantees or
numerical claims from this placeholder.
