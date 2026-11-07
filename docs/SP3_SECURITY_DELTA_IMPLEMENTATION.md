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

## H2 comparators

The memcached variants share pinned upstream `items.c` and `logger.c` and
are created by `prepare_memcached_deployment.py --lru-mode`. `upstream`
passes raw item pointers; `domain` validates that they lie outside U memory;
`extended` registers each live item in T before enqueueing and consumes its
registration at use; `handle` retains the preexisting one-use integer handle.
The separate U fault module forges interior or out-of-object pointer bytes.
A positive security delta requires domain acceptance, an observable changed
T outcome, and Extended rejection before trusted use.

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
python3 tools/test_memcached_deployment.py \
  --out evaluation/results/sp3-security-delta/local-correctness
python3 tools/run_sp3_security_delta.py --scope h1 --post-case-gate \
  --correctness-summary evaluation/results/sp3-security-delta/local-correctness/summary.json \
  --out evaluation/results/sp3-security-delta/local-memcached-h1
python3 tools/verify_sp3_security_delta.py --scope h1 --require-post-gates \
  --results evaluation/results/sp3-security-delta/local-memcached-h1
```

Other independent suites use `--scope h2_memcached`, `--scope h2_yaml`,
`--scope h1_nginx`, `--scope h1_rsync`, or `--scope h1_yaml` after their build
scripts complete. The verifier rejects missing or modified raw evidence,
never treats a prediction as an observation, and writes a JSON verdict and
Markdown report in each result directory. Inspect the raw evidence before
editing threat claims. The paper repository is untouched.
