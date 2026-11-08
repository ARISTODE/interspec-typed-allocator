# Security-delta implementation and reproduction

The preregistered question, decision rules, and predictions are fixed in
[`SP3_SECURITY_DELTA_PLAN.md`](SP3_SECURITY_DELTA_PLAN.md). This document
describes code and evidence collection, not experimental findings. The
implementation belongs to branch `claude/nifty-cray-ik99hh`.

## Trusted checks and limits

`interspec::Runtime` holds trusted metadata for external objects.
`check_external_element_by_address` and `check_external_field_by_address`
validate raw pointers against domain, type, alignment, extent, and field
layout. `unregister_external` revokes a record. The existing token-based
checks remain for interfaces carrying registration tokens. Address-only
checks cannot detect reuse of the same address with matching metadata (ABA),
or a wrong object of the same type without an authenticated expected base.
These guarantees are not asserted.

## H1 comparators

The ordinary fault-only wasm2c modules retain adversarial U fault hooks and
omit typed imports. The Extended variants include tracking and checks. Both
retain the normal T bridge validation. Sanitizer-instrumented T binaries are
excluded from timing. The runner records protocol, stdout, stderr, file-tree
snapshots, binary digests, and exceptions without suppressing failures.

Memcached modes 101 through 110 use legitimate return pointers with the same
U-controlled contents as each corresponding malformed-pointer case where
possible. The verifier checks T copy digests, liveness, and protocol results;
unmatched cases stay inconclusive. With `--post-case-gate`, the existing
50-case memcached correctness suite repeats after each scenario. The nginx,
rsync, and yaml verifiers compare results against legitimate executions and
report incomplete or unexpected observations.

The memcached runner defaults to `--pointer-census` **off** for the controlled
fault comparison, while keeping trusted copy digests, check decisions, fault
markers, and process outcomes. Enabling the optional high-volume census adds
substantial logging and is a separately labeled diagnostic, not silently
intermixed with the primary comparator. The CI first runs
`smoke_sp3_memcached_h1.py` to require clean legitimate operation from both
fault-only binaries before executing the expensive fault and correctness
matrix. `--fail-on-incomplete` makes invalid controls fail evidence CI; a
genuinely inconclusive observed outcome remains in the report.
After the primary H1 matrix, CI also executes the same H1 faults with
`--pointer-census` in a separately named evidence directory. The independent
verifier checks those cases without treating the extra logging as an
interchangeable primary measurement. The ordinary 50-case post-scenario
correctness gate remains attached to each primary H1 case.
H2 memcached LRU runs use the pointer census in their primary evidence, with
an independent verifier requirement for a structured census record per run.

Sanitizer-specific build provenance: pinned memcached upstream source has a
`NEED_ALIGN` padding expression missing parentheses in `logger.c`. The
sanitizer `configure` run enables this path, unlike the ordinary build, and
was observed to produce padding rejected by the existing T logger validator
in clean, fault-mode-zero controls. `patch_memcached_sanitizer_logger.py`
corrects the record alignment arithmetic only in the security experiment's
copied `logger.c` sources. This makes ASan/UBSan instrumentation compatible
with the original logger semantics; it does not relax any trusted format
check or change normal application/performance binaries.

## H2 comparators

The memcached variants share pinned upstream `items.c` and `logger.c` and
are created by `prepare_memcached_deployment.py --lru-mode`. `upstream`
passes raw item pointers; `domain` validates that they lie outside U memory;
`extended` registers each live item in T before enqueueing and consumes its
registration at use; `handle` retains the preexisting one-use integer handle.
The separate U fault module forges interior or out-of-object pointer bytes.
A positive security delta requires domain acceptance, an observable changed
T outcome, and Extended rejection before trusted use.

### Post-review comparator revision

The raw `domain` and `extended` source transforms now share the deployed
record-extent guard before either reads an LRU entry. This rejects an empty
or partial record sequence before the upstream unsigned `todo` loop. The
explicit `upstream` reference stays unchanged. This is common framing
validation, not additional object identity enforcement in one comparator.
The archived runs at `097e650` and `215b4bd` predate this revision: retain
their source SHAs and evidence and rerun the affected application matrix
before attributing results to the revised implementation.

Raw H2 is a narrow pointer-policy experiment, not a generally hardened
replacement for the deployed handle path. Its `item*` registration does
not authenticate the accompanying `hv` used for locking. Pointer type,
domain and extent checks alone do not establish item/hash consistency or
general integrity of U-controlled contents. Adding a trusted identity/hash
binding to the domain-only comparator would change the defense under test;
it must be a separately labeled configuration, not silently folded into
these results. Production continues to use the one-use handle, which
checks the trusted item/hash association.

The independent H2 verifier now requires a matching mode and target in
every comparator's fault marker and cannot classify a run with an Extended
sanitizer finding as prevented harm. Replaying both archived confirmation
and current-head raw H2 evidence under this stricter rule preserves mode
11's security delta and mode 12's inconclusive result. This is evidence
reanalysis, not an application rerun of the revised extent guard.

The libyaml T driver exercises the real `yaml_parser_set_input` read-handler
API and RLBox domain predicate. Project-authored trusted test code supplies
untracked, revoked, wrong-type, same-type, and identity-mismatched pointers.
This probes the policy on that API, not an upstream or wasm2c U-authored
attack. The nginx/OpenSSL `ex_data_ptr` case is deferred.

## Reproduce and audit

The GitHub Actions workflow `.github/workflows/sp3-security-delta.yml`
executes H1 on all four application boundaries and H2 on both available T
pointer integrations on Ubuntu 24.04. Raw evidence is uploaded even if a
case or build fails. An appropriately provisioned Linux host can also run:

```bash
bash scripts/build_memcached_security_delta.sh
python3 tools/smoke_sp3_memcached_h1.py \
  --out evaluation/results/sp3-security-delta/local-smoke
python3 tools/test_memcached_deployment.py \
  --out evaluation/results/sp3-security-delta/local-correctness
python3 tools/run_sp3_security_delta.py --scope h1 --post-case-gate \
  --correctness-summary evaluation/results/sp3-security-delta/local-correctness/summary.json \
  --out evaluation/results/sp3-security-delta/local-memcached-h1
python3 tools/verify_sp3_security_delta.py --scope h1 --require-post-gates \
  --fail-on-incomplete \
  --results evaluation/results/sp3-security-delta/local-memcached-h1
```

Other independent suites use `--scope h2_memcached`, `--scope h2_yaml`,
`--scope h1_nginx`, `--scope h1_rsync`, or `--scope h1_yaml` after their build
scripts complete. The verifier rejects missing or modified raw evidence,
never treats a prediction as an observation, and writes a JSON verdict and
Markdown report in each result directory. Inspect the raw evidence before
editing threat claims. The paper repository is untouched.
