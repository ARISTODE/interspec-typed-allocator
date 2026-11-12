# Throughput and latency measurement modes

The extended client accepts:

`client PORT SECONDS CLIENTS PIPELINE VALUE_BYTES KEYS GET_PERCENT [TOTAL_OPERATIONS [WORKLOAD_MODE [SEED [MEASUREMENT_MODE [SAMPLE_EVERY [SAMPLE_CAP_PER_CLIENT]]]]]]`

Old direct calls retain `legacy` workload and `full` measurement defaults. The updated timing collectors explicitly default to corrected `independent-v1` and `count-only`; use `--measurement-mode` to select another mode. This is a measurement-method change and must not be silently pooled with historical runs.

- `count-only`: validate every expected response and increment a local completion counter. No latency timestamp/vector reservation per response. Latency quantiles/max are JSON null, `latency_valid=false`, scope unavailable. Timed wall deadline checks and network work remain.
- `full`: retain every response's batch-send-to-response-validation duration; the old instrumentation remains available as a sensitivity control. Dynamic vector growth can interfere with measured throughput.
- `sampled`: select indexed operation IDs using a third domain-separated pseudorandom draw, distinct from key and GET/SET generation. Default probability is approximately 1/1024; configurable via SAMPLE_EVERY. A batch start timestamp is acquired only if needed, and a completion timestamp only for a selected response. Each thread preallocates a bounded buffer before the ready barrier (default cap100000). It never grows past the cap. All responses, selected or not, are validated and counted.

Sample selection is deterministic for an indexed fixed-work set regardless of worker/pipeline assignment, not a proof of statistical independence or identical execution ordering. Only selected responses contribute to quantiles. Their duration is measured from the send of their entire pipeline batch until their own validated completion, not individual request service time or open-loop latency. Sampled max is the maximum observed sample, not whole-run max. Do not substitute this pass's latency for another count-only pass without explicitly labeling it independent.

Metadata includes mode, rate, per-client cap, selected/stored/dropped counts and scope. If any thread exceeds its sample cap, or no sample is observed, all latency quantiles are null and `latency_valid=false`; counts still reveal the diagnostic and throughput remains measured. This avoids reporting a time-biased first-cap subset as representative. Full mode has no cap. Count-only has no samples. Collectors preserve nulls and report renderers print unavailable instead of zero. Mixed measurement-mode/sampling summaries are rejected where combined.

`timed_client_cpu_s` uses CLOCK_PROCESS_CPUTIME_ID immediately before releasing clients through final joins. It excludes post-run latency merging/sorting; it includes all client threads plus main-thread coordination during that interval. It is not server CPU and does not alone establish headroom or absence of individual-thread bottlenecks.

Functional validation includes sampled cap behavior, no latency allocation in count-only, independently selected GET/key distribution checks over two million operations, stable sample count across batching, seven live-server tests with identical completed GET/SET counts across modes/client configurations, overflow suppression, count-only collector null-summary handling and the full default CTest suite. Empirical capacity/equivalence tests are a separate gate; choosing sampled mode does not automatically make instrumentation negligible.
