# Handoff: Extended SP3 security-delta experiments (issue 1)

**State on branch `claude/nifty-cray-ik99hh`:** plan and predictions committed;
memcached builds and correctness gate verified on a cloud VM. The experiment
runs themselves (steps 2 and 3 below) have **not** been started.

Read first:

1. [`docs/SP3_SECURITY_DELTA_PLAN.md`](SP3_SECURITY_DELTA_PLAN.md): hypotheses,
   configurations, outcome measures, decision rules and pre-registered
   predictions. Do not edit its prediction tables; record results elsewhere.
2. `integration/memcached_server/bridge.cpp`, `bipbuffer_u.c`,
   `tools/prepare_memcached_deployment.py`, `tools/test_memcached_deployment.py`,
   `tools/test_u_storage_faults.py`.

## Why this exists

The paper's SP3 (pointee domain integrity) accepts a T-domain pointer if it is
outside sandbox memory. Extended SP3 adds object-level checks, but the current
implementation applies them only to U-domain pointers, where the plan argues
they may not change T's outcome. These experiments decide which claim the
evidence supports. See the plan, section 2.

## Done

| Step | Evidence |
| --- | --- |
| Plan and predictions | commit `4ac8eaf`, `docs/SP3_SECURITY_DELTA_PLAN.md` |
| memcached build from clean `be9947e`, upstream `2d51e36` | all 7 binaries: native, native-debug, rlbox-only, tracked-no-check, interspec, interspec-debug, diagnostics |
| 50-case correctness gate | 50/50 passed on a 4-vCPU Ubuntu 24.04 cloud VM |

## Reproduce the baseline

```bash
sudo apt-get install -y autoconf automake build-essential libevent-dev libio-socket-inet6-perl
python3 -m venv .venv && .venv/bin/pip install 'cmake>=3.30,<4'
PATH="$PWD/.venv/bin:$PATH" INTERSPEC_MEMCACHED_WORK=/tmp/mc INTERSPEC_BUILD_JOBS=4 \
  bash scripts/build_memcached_deployment.sh
python3 tools/test_memcached_deployment.py --work /tmp/mc --out /tmp/mc-results/correctness
```

The pinned `rlbox_wasm2c_sandbox` requires CMake 3.30 or newer. Ubuntu 24.04
ships 3.28; GitHub's `ubuntu-latest` runners already have a newer CMake.

## Remaining work

### Step 2: H1 on U-domain pointers (all four boundaries)

1. Add an RLBox-only build that contains the existing fault hooks
   (`INTERSPEC_FAULT_TESTS`) but no InterSpec tracking or checks. Keep it a
   separate binary, never used for timing. Build T with AddressSanitizer and
   UndefinedBehaviorSanitizer.
2. Run each existing fault mode listed in the plan's H1 table against that
   build and against `memcached-diagnostics` (Extended SP3).
3. Record the outcome measures in plan section 4 for every case, and the
   legitimate-pointer comparison the H1 decision rule requires.
4. Repeat for rsync/popt, nginx/libpcre and yaml/libyaml using their existing
   fault hooks and drivers (`scripts/run_rlbox_wasm2c_poc.sh`,
   `scripts/run_p7c_wasm2c.sh`, `integration/*`).

**Done when:** every case in the H1 table has a recorded outcome for both
configurations, with raw logs and SHA-256 hashes, and an independent verifier
script re-derives each verdict from the raw logs.

### Step 3: H2 on T-domain pointers

1. **memcached LRU bump entries.** Build three variants of the LRU path:
   upstream `items.c` unchanged, the paper's domain-only check, and an
   Extended-SP3 variant that registers each queued item as a T-domain object
   and checks and revokes it when the entry returns. The current one-use
   handle bridge is a fourth reference variant.
   The runtime has no way to look up a T-domain registration by address
   (`check_nonheap_*` require the token), so add that API to
   `include/interspec/runtime.h` with unit tests in
   `tests/runtime_object_layout.cpp`.
2. **libyaml read handler.** Add a T driver that uses
   `yaml_parser_set_input(parser, handler, data)` with a T context object, and
   evaluate the domain-only and Extended-SP3 checks on the returned `data`.
   Label the driver as project-authored T code.
3. **nginx/openssl `ex_data_ptr`** is deferred: no OpenSSL wasm2c build exists
   in this repository.

**Done when:** each H2 row in the plan has recorded outcomes per variant,
using the same outcome measures and verifier requirements as step 2.

### Step 4: record and reconcile

1. Write results to `SP3_SECURITY_DELTA_RESULTS.md` and raw artifacts under
   `evaluation/results/sp3-security-delta/`. Mark every deviation from the
   predictions.
2. Add a CI workflow that rebuilds from pinned revisions and reruns the
   experiments with artifact upload.
3. Rewrite the threat model and Extended-SP3 claim in this repository's docs
   and evidence ledger to match the results. Do **not** modify the paper
   repository `ARISTODE/Automatic-Access-Policy-Enforcement`.
4. Open a draft PR into `main`. Its description must state that the branch
   also carries the 72 commits of `experiment/original-source-provenance-20261031`.

## Constraints

* Fault-injection and sanitizer binaries are never used for timing.
* Keep failed and unexpected runs; never rerun until results match predictions.
* `tracked_no_check` is a performance baseline, not a security comparator.
* Same-type substitution between two live objects is a documented scope limit,
  not a failure.
