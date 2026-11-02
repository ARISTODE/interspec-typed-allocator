# InterSpec evidence ledger

**Last reviewed:** 2026-11-02 UTC, against GitHub PR metadata and referenced repository reports. This ledger deliberately distinguishes actual observations from inferred guarantees. Update links/commit SHA after new runs; preserve prior runs instead of replacing them silently.

Status meanings:

* **Verified within stated scope:** source, test, raw evidence and stated acceptance conditions documented; not universal or publication-ready by default.
* **Hosted reference:** reproducible/tested in CI or other non-dedicated environment, **not** controlled paper performance.
* **Prototype only:** compiled/runtime exercise exists, but real-application deployment not demonstrated.
* **Pending/blocked:** evidence required for the claim does not yet exist.

## Original-source-only pointer provenance

| Evidence | Observations | Status and what they do NOT establish |
| --- | --- | --- |
| [Draft PR #24](https://github.com/ARISTODE/interspec-typed-allocator/pull/24), [source audit](../tools/source_origin/README.md) | **14 candidate original upstream application API expressions**: nginx 3 stack outparams + 2 static error result candidates; rsync 3 argv/alias `poptBadOption` returns; memcached 5 stack candidates + 1 static literal. | Verified selected source candidates; **not** an exhaustive pointer-field denominator, execution frequency or unchanged raw address crossing. |
| [Memcached native CI 41343983340](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41343983340) | At six original input sites: 208 stack, 1 readonly literal events; 18 heap-interior and 198 null returns, 425 selected records total. Native protocol parity passed. | Verified selected native event pilot, not every pointer or isolated transport. |
| [Nginx native CI 41345188937](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41345188937) | Five stack outparam events, one readonly PCRE8 error-string return, eight null/unresolved records attributed to upstream source. | Verified original native pilot. No unchanged T stack pointer transit shown. |
| [Rsync isolated-API source CI 41345859550](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41345859550) | Two original main-rsync `poptBadOption` results had **unresolved memory mappings**. One additional auxiliary `tls` return was stack. | Unresolved remains unresolved. Three `poptStrerror` host-helper results are **excluded** from isolated return counts. |
| [SP3 source and isolation mapping, PR #24](https://github.com/ARISTODE/interspec-typed-allocator/pull/24) | Memcached T stack inputs and T literals copied to U; Nginx T stack outparams stay T, U error bytes staged in tracked storage and copied to T; rsync U string bytes checked and copied to T. | Reviewed selected bridges. No evidence yet that an original raw T stack address crossed unchanged. Complete indirect-transit census pending. |

**Excluded from original-source prevalence:** instrumentation, wrapper-generated pointers, synthetic corruption values, drivers, host-only helpers, and unmatched native call sites. Earlier 1,818 wrapper/adapter pointer observations (1,089 stack, 26 ELF, 442 tracked heap, 261 unknown) are **retired for the original-source denominator**. Unknown does not mean heap. Named global objects and nested pointers require separate enumeration. Project-authored YAML driver is not original external application code.

## Normal behavior and security

| Evidence | Result | Scope |
| --- | --- | --- |
| [Memcached native vs isolated run 41354003332](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41354003332) | Eleven checked protocol/watch-event fields matched across four modes for tested traffic. | Verified tested workload fields, not all operation sequences. |
| [Nginx strict parity and corruption run 41355456516](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41355456516), [PR #25](https://github.com/ARISTODE/interspec-typed-allocator/pull/25) | Four modes matched HTTP outputs; two valid and three malformed configurations had zero diagnostic text/offset mismatches after fix. Four injected U metadata corruptions rejected (extent, NUL termination, offset, control byte). | Verified selected PCRE8 configurations and four negative cases. Original baseline had nine precise-diagnostic mismatches. |
| [Rsync native vs isolated run 41345859544](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41345859544), [SP3 diagnostics](../SP3_DIAGNOSTICS.md) | Six paired workloads and three file-manifest comparisons; actual P4c bridge corruption tests and known functional regression fix. | Verified tested observables, not all rsync features. |
| [YAML evaluation run 41172234996](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41172234996) | Six-field semantic signatures matched across four modes; 1,036 events and 1,024 scalars per mode in tested driver. | Verified project-authored driver only. |
| [PR #26](https://github.com/ARISTODE/interspec-typed-allocator/pull/26), [runtime design](SP3_TYPED_POOL_NONHEAP.md), `tests/runtime_object_layout.cpp` | Typed array stride/alignment, exact element/field ranges, optional expected-element identity; external trusted T heap, stack and U global registrations and revocation exercised in C++ runtime tests. | **Prototype/unit tests**: application bridges not systematically connected. U stack registration requires authenticated scope metadata. |

A successful malicious-pointer rejection test does not prove comprehensive pointer control, object content integrity, same-type identity without binding, or complete temporal safety.

## Hosted benchmark and publication readiness

| Evidence | Observed data | Publication status |
| --- | --- | --- |
| [Hosted evidence audit PR #27](https://github.com/ARISTODE/interspec-typed-allocator/pull/27), [audit report](../evaluation/HOSTED_REFERENCE_AUDIT_20261102.md) | Independently checked **400 raw application samples**, 12 workloads, four variants: Memcached 120, Nginx/PCRE8 40, YAML 60, rsync 180. Recomputed per-workload paired overheads and checked retained ZIP hashes. | **Hosted reference only.** Samples originate from different environments, and new pool/nonheap changes are not in these binaries. |
| [Memcached completion CI 38092306794](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/38092306794), [evaluation ledger](../EVALUATION_COMPLETION.md) | 120 paired hosted samples, 50-case gate; separately 2,070 successful SP3 checks/1,000 LRU pairs in a declared 200k-op diagnostic profile; 686 boundary samples and 195 runtime samples independently verified in their stated protocols. | Hosted reference/diagnostic, not final controlled throughput or global overhead. |
| [Controlled protocol](../CONTROLLED_EVALUATION.md) and [draft PR #28](https://github.com/ARISTODE/interspec-typed-allocator/pull/28) | Manual-only, SHA-pinned workflow staged for full Memcached, Nginx, rsync/P11, YAML and microbenchmarks. | **Pending:** not dispatched; no confirmed dedicated >=8-physical-core host with 4 server + 4 client distinct cores. Runner infrastructure required. |
| Manuscript historical figures | SP1 42.3% (3,179/7,523), SP2+SP3 58.8% (4,426/7,523), pointer coverage 99.4% (1,955/1,966), earlier 7.5% geomean and ZIP/libzip row. | **Not revalidated against final implementation/protocol.** No new combined geomean or ZIP number should be inferred. |

Nginx hosted runs have shown different near-zero and materially positive overheads under different conditions. Do not select the favorable sample as the paper result. A dedicated controlled host, full repetition counts, matched code versions, original code-vs-bridge provenance, independent verifiers, correct sign convention, and fixed inputs remain mandatory. Docker is useful for reproducible builds/correctness but does not by itself certify an isolated measurement host.

## How to add new evidence

For every new completed claim, record: claim and precise scope; source branch and 40-character SHA; pinned upstream revision; exact build/test commands; hardware/runner configuration; native/isolated modes and inputs; CI run URL and artifact name/digest (or equivalent local archive SHA256); raw observed counts; independent verifier status; any failed or excluded runs; and a statement of limitations. Keep future publication-readiness decisions separate from successful CI test status.
