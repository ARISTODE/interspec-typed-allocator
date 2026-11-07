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

H1 memcached/nginx and H2 libyaml are still being collected or repaired.
Do not treat this partial YAML result as a global H1 conclusion.

## Verified H1 rsync/popt observations

[Workflow 42425295349](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42425295349)
retained [48 raw executions](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42425295349/artifacts/13595014181)
across 16 rsync/popt fault scenarios, including the copyback control. The
independent verifier passed again on the downloaded artifact.

Ten cases had the same trusted output files and stdout as the legitimate
run, with no trusted sanitizer report. Six were inconclusive because their
output changed; none generated a trusted sanitizer report. These are H1
observations of the fault-only comparators, not proof that changing U-supplied
command-line content is harmless in every possible context.

The initial nginx H1 artifact contains 45 executions, but a known upstream
zero-length `ngx_pstrdup` call triggered an unrelated UBSan nonnull-attribute
diagnostic during ordinary startup. Those runs cannot support a security
conclusion. They are preserved while a narrowly adjusted sanitizer build
is prepared with ASan and the other UBSan checks still enabled.

## First memcached H2 observations and H1 validity warning

The initial memcached run
[`42423558556`](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42423558556)
preserved [52 raw executions and 12 repeated correctness gates](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42423558556/artifacts/13595271042).
The 40-case H1 and 12-case H2 collections each produced a verified JSON
summary. Generation of the H2 Markdown report failed on an output-key bug;
the logged raw data and summary remain available. This reporter bug is fixed
in the working implementation and awaits a new CI run.

| H2 LRU mutation | Domain-only result | Extended SP3 | Existing one-use handle | Initial interpretation |
| --- | --- | --- | --- | --- |
| Interior `item* + 1` | Accepted, then T ASan error | Rejected `out_of_bounds` before use | Rejected unknown handle | **Observed security delta** |
| Outside object `item* + 65536` | Accepted; no observed T harm | Rejected `untracked` | Rejected unknown handle | **Inconclusive** as a harm-prevention claim |

These outcomes are for injected raw LRU item pointer bytes, not naturally
occurring exploitation. Because the existing one-use handle also rejects the
corruption, this demonstrates protection supplied by the new general check,
not a stronger guarantee than the existing application-specific handle.

The initial H1 memcached run also exposed a test-harness validity defect:
its nominally legitimate RLBox fault-only cases exited on the T logger's
`malformed_record` rejection under the chosen watcher traffic. Even though
the original 50/50 application correctness gate passed, H1 equivalence must
**not** be inferred from two failing comparator runs. The replacement runner
uses the proven three-event watcher workload, and the verifier now requires
an independently healthy legitimate run before declaring a security delta
absent. The first H1 summary remains preserved as diagnostic evidence only.

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
