# Controlled publication measurement handoff

Status: ready to identify and inspect a host, not executed. Hosted references
must remain labeled as such. No cloud machine has been provisioned or billed.

Use a dedicated Linux host with at least eight available physical CPU cores,
enough memory for the applications/toolchains and adequate disk space for all
raw artifacts. Supply the existing self hosted runner label or SSH target.
CPU numbers below are examples and must be selected from the actual topology;
server and client sets must not share physical cores. Record the host owner,
OS/toolchain versions, virtualization, frequency/power policy, background load,
thermal conditions, and any limits. Save an inventory before and after the run.

Run `tools/publication_host_preflight.py --server-cpus SERVER_SET
--client-cpus CLIENT_SET --operator-confirms-dedicated --out host-before.json`
only after the operator establishes exclusive use. The tool is read only. It
checks affinity, overlapping cores, visible power policy, quota and tools. Its
output never sets publication readiness true. Missing frequency visibility must
be resolved with the host operator rather than guessed.

## Protocol and execution order

1. Check out the exact reviewed implementation commit, require a clean source
   tree, and create a fresh experiment output directory. Preserve all failed
   runs and do not overwrite prior artifacts. Build all four memcached variants
   with `scripts/build_memcached_deployment.sh` and run the complete 50 case
   application gate. Save the build manifest, stdout/stderr and hashes.
2. Run the six scenario matrix using `tools/benchmark_memcached_matrix.py`
   with `--preset paper --include-tracking --server-cpus SERVER_SET
   --client-cpus CLIENT_SET --correctness-summary CORRECTNESS_JSON --out NEW_DIR`.
   This is 360 samples, fifteen paired repetitions, thirty second windows and
   five second warmups. The traffic alone takes 3.5 hours. Run the independent
   `verify_memcached_matrix.py` against this output before deriving paper tables.
3. Run the fixed diagnostic profiles and `verify_memcached_profile.py` on this
   same host, retaining profile key counts and the asynchronous drain interval.
   Diagnostic elapsed time is not performance evidence.
4. Build the separate boundary executables with
   `scripts/build_memcached_boundary_bench.sh`. Run
   `tools/run_memcached_boundary_bench.py --cpu ONE_SERVER_CPU --repetitions 15
   --iterations 1000000 --out NEW_DIR`, then the independent boundary verifier.
   Rerun all 39 runtime configurations using `tools/run_runtime_microbench.py`
   with fifteen repetitions, one million iterations and recorded CPU placement.
   For concurrency configurations, provide enough server CPUs for the declared
   thread counts and label any deliberate oversubscription.
5. Build and gate actual nginx with `scripts/build_nginx_deployment.sh` and
   `tools/test_nginx_deployment.py`. Collect all four variants with
   `tools/benchmark_nginx.py --seconds 30 --warmup-seconds 5 --repetitions 15
   --threads 4 8 --connections 100 --server-cpus SERVER_SET
   --client-cpus CLIENT_SET --correctness CORRECTNESS_JSON --out NEW_DIR`.
   State server worker count separately from client threads. Preserve the
   PCRE8 interpreter scope; this run does not establish TLS/PCRE2/JIT results.
6. Rerun `scripts/run_p11_wasm2c_performance.sh NEW_DIR` with
   `INTERSPEC_P11_REPETITIONS=15`, `INTERSPEC_P11_WARMUPS=2` and
   `INTERSPEC_P11_CPU=ONE_SERVER_CPU`. Rerun the full YAML driver through
   `scripts/run_yaml_libyaml_evaluation.sh NEW_DIR`, pinning its process tree
   with taskset and recording that choice; use fifteen pairs, two warmups,
   a 1 MiB document and 1,000 parses per sample. Preserve the exact inputs and
   correctness/security outputs. These scripts own their named temporary
   build directories, so use a fresh experiment TMPDIR.
7. Check load generator limits before interpreting throughput. Record client
   and server CPU use and test whether additional available client CPU capacity
   changes the result at the same workload. Report the one client workloads as
   such; do not claim server saturation without supporting evidence.
8. Validate all raw sample counts, correctness bindings, losses, per-pair
   arithmetic, outliers and run variation. Do not silently remove unfavorable
   samples or retry until an attractive median appears. A rejected run remains
   archived with its reason; a protocol change creates a distinct experiment.

The original ten boundary suite still requires the provenance, policy-control,
coverage and PoC work in EVALUATION_COMPLETION.md. Newer Extended SP3 experiments
do not establish the original SP1/SP2/SP3 paper claims.
