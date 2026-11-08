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

H1 memcached remains under control-validity repair. The other H1 boundaries
and the project-authored H2 libyaml driver have verified observations below.
Do not treat the partial YAML result as a global H1 conclusion.

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

## Verified H1 nginx/libpcre observations

[Workflow 42425810424](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42425810424)
retained [45 raw executions](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42425810424/artifacts/13595598538)
for 15 fault scenarios. Eight yielded the same observable trusted result as
the legitimate nginx run. Seven were stopped by the existing trusted bridge
format or extent checks. No trusted sanitizer error was observed. The more
conservative verifier with `--fail-on-incomplete` passed independently against
the downloaded artifact and reported no prediction deviation.

An earlier nginx run was invalid because an upstream zero-length `ngx_pstrdup`
call triggered a nonnull-attribute UBSan diagnostic during ordinary startup.
The successful comparator disables only that false-positive check, retaining
ASan and the remainder of UBSan; the first run remains archived. The new
results apply to the tested PCRE return paths and do not cover nginx/OpenSSL
or every possible U-domain pointer.

## First memcached H2 observations and H1 validity warning

The initial memcached run
[`42423558556`](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42423558556)
preserved [52 raw executions and 12 repeated correctness gates](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42423558556/artifacts/13595271042).
The 40-case H1 and 12-case H2 collections each produced a verified JSON
summary. Generation of the H2 Markdown report failed on an output-key bug;
the logged raw data and summary remain available. This reporter bug was fixed
before later CI executions; the original artifact remains archived.

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

The later [run 42425295349](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42425295349)
also collected and verified H1 memcached records under a three-event
watcher workload. Eight role-1 legitimate cases still rejected
`malformed_record` in the instrumented fault-only comparator and therefore
remain **incomplete**, not validated no-delta evidence. Two role-3 LRU
format-control cases had matching outcomes. The strict verifier rejected
the eight invalid controls on independent local replay. The next evaluation
will run a fail-fast legitimate smoke and remove optional high-volume
pointer-census I/O from both primary comparators; separate census diagnostics
remain available.

The [fail-fast smoke in run 42427415881](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42427415881)
[archived both failing legitimate controls](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42427415881/artifacts/13595748739)
even with pointer census disabled. The run's compiler configuration logs
identify a specific upstream sanitizer-only compatibility issue:
`checking for alignment... none` in the ordinary build but `need` under
ASan/UBSan. The pinned `logger.c` has an unparenthesized `NEED_ALIGN`
expression, `sizeof(logentry) + e->size % 8`; on this build it can generate
an excessive padding byte that T's existing record validator rejects.
The sanitizer-only source build now computes
`(sizeof(logentry) + e->size) % 8`, without disabling the logger validator,
changing the ordinary timing builds, or erasing the invalid runs. This
diagnosis still needs a clean hosted legitimate-control rerun.

## Verified H2 libyaml read-handler driver

[Run 42425295349](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42425295349)
also preserved [12 libyaml T-context executions](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42425295349/artifacts/13595569181).
Local replay of the independent verifier passed.

| T-context scenario | Domain-only behavior | Extended SP3 behavior | Interpretation |
| --- | --- | --- | --- |
| Legitimate | Accepted, parsed `trusted` | Accepted, parsed `trusted` | Valid control |
| Untracked T object | Accepted, parsed `altered` | Rejected | Modeled security delta |
| Revoked T object | Accepted, parsed `altered` | Rejected | Modeled security delta |
| Wrong type | Accepted, parsed `altered` | Rejected | Modeled security delta |
| Same type, different object | Accepted, parsed `altered` | Accepted | Expected identity limitation |
| Same type, authenticated expected base | Accepted, parsed `altered` | Rejected | Modeled security delta with identity binding |

The driver exercises the actual `yaml_parser_set_input` callback API and
RLBox domain predicate, but the pointer mutation is explicitly
**project-authored T-side test code**, not a malicious value crossing an
upstream libyaml wasm2c boundary. Its security-delta result is a mechanism
demonstration, not evidence of an existing libyaml exploit.

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
