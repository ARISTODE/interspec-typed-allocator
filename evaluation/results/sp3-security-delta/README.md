# Extended SP3 security-delta evidence index

The preregistered predictions are frozen in
[`docs/SP3_SECURITY_DELTA_PLAN.md`](../../../docs/SP3_SECURITY_DELTA_PLAN.md).
Interpretations and known limits are in
[`SP3_SECURITY_DELTA_RESULTS.md`](../../../SP3_SECURITY_DELTA_RESULTS.md).
The raw files are generated under this directory by the dedicated GitHub
Actions job and preserved as workflow artifacts, rather than committing
fault/sanitizer binaries or large generated server logs into Git history.

## Independently verified primary run

Workflow: [42427969783](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42427969783).
Source commit: `5735a1ba0a616915b57cc51fa314f686d39ca8c7`.
All five dedicated jobs passed on Ubuntu 24.04. The six planned available
application comparators yielded 172 raw executions. The memcached suites
additionally performed one baseline 50-case gate and 12 post-scenario 50-case
gates, all passing. Every artifact contains a `collection.json`,
`provenance.json`, immutable raw process/protocol streams, and an independently
generated `verified-summary.json` and Markdown report.

| Evidence | Raw executions | Artifact ID | GitHub ZIP digest (SHA-256) |
| --- | ---: | --- | --- |
| Memcached H1, H2 and libyaml H2 | 40 + 12 + 12 | [13597002131](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42427969783/artifacts/13597002131) | `568d81572611b6debccb1a153331b1681cada3b91ddd02351dc5730e3799b751` |
| Rsync/popt H1 | 48 | [13596635440](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42427969783/artifacts/13596635440) | `73858ec65286775d6e3530fa850137f6b7cf70c7eb588e5bf2b059452afc7534` |
| YAML/libyaml H1 | 15 | [13596147698](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42427969783/artifacts/13596147698) | `8017624107c1dd66f430f7a5969bdf16ee127bb2154e3549b9078b5cf7928ef6` |
| Nginx/PCRE8 H1 | 45 | [13595824985](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42427969783/artifacts/13595824985) | `dbcbd63e81a40d27f03840a6bb8e74ad6ac1b10ca44c89dc479d87ee0466690f` |

Primary memcached H1: two `no_observed_delta`, eight `inconclusive`, none
`T_sanitizer_harm`, none `incomplete`. The predicted Extended rejection codes
all matched; separately, RLBox-only exited instead of continuing service in
five modes (1, 3, 4, 9, 10), contradicting a preregistered availability
prediction. These were existing trusted logger/staging rejections, not
observed sanitizer harm. H2 raw LRU interior-pointer tampering
showed a security delta against domain-only checking; the existing one-use
handle also rejected it. The libyaml T read-handler outcome demonstrates
the new check mechanism on project-authored trusted pointer corruption,
not a sandbox-to-trusted attack.

The earlier invalid runs are deliberately retained. In particular,
[42427415881](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42427415881)
captures both invalid H1 no-fault controls in sanitizer-only builds before
correcting the pinned upstream `logger.c` `NEED_ALIGN` arithmetic. Do not use
those failed controls as no-delta evidence.

## Replay

Download and extract the corresponding workflow artifact, preserving its
`evaluation/results/sp3-security-delta/` subtree, then independently run:

```bash
python3 tools/verify_sp3_security_delta.py --scope h1 \
  --results evaluation/results/sp3-security-delta/memcached-h1 \
  --require-post-gates --fail-on-incomplete
python3 tools/verify_sp3_security_delta.py --scope h2_memcached \
  --results evaluation/results/sp3-security-delta/memcached-h2 \
  --require-post-gates --fail-on-incomplete
python3 tools/verify_sp3_security_delta.py --scope h2_yaml \
  --results evaluation/results/sp3-security-delta/yaml-t-context
```

For other H1 applications, use `--scope h1_rsync`, `h1_yaml`, or `h1_nginx`
with each corresponding artifact result directory and
`--fail-on-incomplete`. This workflow also contains a separately labeled
pointer-census repeat, whose result must be verified independently before
being treated as corroborating evidence. GitHub Actions artifact retention
is finite; reproducibility requires preserving downloaded archives or
rerunning the pinned workflow.
