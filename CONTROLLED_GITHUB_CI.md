# Controlled InterSpec GitHub CI handoff

**Status:** Workflow staged, not dispatched. There is no confirmed dedicated 16-core
runner assigned to `ARISTODE/interspec-typed-allocator`. No paid runner
minutes have been consumed by this workflow. The official paper repository is
unchanged.

The workflow `.github/workflows/controlled-publication-evaluation.yml` runs
the full, unshortened experimental protocols from an immutable source SHA.
It uses `workflow_dispatch` only and does not run on pull requests or pushes.
GitHub requires the workflow file to exist on the default branch before the
manual **Run workflow** button is available.

## Required infrastructure

1. Provision an isolated Ubuntu runner with at least eight **physical** cores,
   or a larger core count if the workload competes with system services. Confirm
   exclusive use during the run. GitHub's standard `ubuntu-latest` runner is
   inadequate for the 4+4 physical core server/client protocol.
2. Provide the actual runner label. GitHub-hosted 16-core larger runners require
   an organization using GitHub Team or Enterprise Cloud, plus runner setup by
   an organization administrator. `ARISTODE` currently owns this repository as
   a **personal account**. A personal public repository cannot use those larger
   runners directly. An authorized self-hosted Ubuntu runner is an alternative.
3. Record processor topology using `lscpu -e=CPU,CORE,SOCKET,NODE,ONLINE`.
   Supply four distinct server-core CPU IDs and four other non-sibling client
   CPU IDs. Do not assume adjacent Linux CPU numbers imply separate cores.
4. Use the reviewed 40-character source commit, initially
   `be9947e8bd23213a6280c8ca272c1db4b7d2b90e`.
   Explicitly confirm the host is dedicated. The initial validation job rejects
   missing inputs, moving source refs, standard 4-vCPU labels, and unconfirmed
   exclusive use.

## Workflow

The five workload jobs run **serially**, retaining complete raw samples,
application correctness evidence, source commit, host inventory before and
after, and SHA-256 checksums.

| Job | Protocol | Evidence |
| --- | --- | --- |
| Memcached | Six scenarios, four modes, fifteen 30-second pairs, five-second warmups | 360 raw throughput samples, 50-case correctness gate, independent matrix and profile verifiers |
| Nginx/PCRE | Four modes, two wrk thread settings, fifteen 30-second pairs, five-second warmups | 120 throughput samples, matched binary hashes, response validation, correctness and parity audits |
| Rsync/popt | P11 native, RLBox-only, tracked-no-check, Extended SP3, fifteen repetitions and two warmups | Complete-process timings, provenance, correctness gate |
| YAML/libyaml | Four modes, 1 MiB input, 1,000 parses, fifteen repetitions and two warmups | Raw timings, semantic hashes and parity audit |
| Microbenchmarks | Fifteen repetitions of one million operations | 39 runtime configurations and four-mode wasm2c boundary timing with independent verifier |

A runner is freshly provisioned for each GitHub-hosted job. Measurements
within one job are paired on that job's host. **Do not compute a cross-job
geometric mean or claim a single-machine comparison** without additional
controlled evidence. The same restriction holds if a self-hosted pool moves
jobs between machines.

The workflow explicitly refuses overlapping CPU sets, insufficient physical
cores, missing tools, and unverifiable source SHA. Lack of visible CPU
frequency policy is retained in the host report but is not used to silently
promote observations to publication-ready measurements.

## Validity and data provenance

The standalone original-source pointer studies distinguish original upstream
call sites from the adapters we wrote. Wrapper-created stack/global variables
are excluded from **original-source** pointer counts. Pointer observations at
trusted adapters are useful diagnostic evidence but must not be merged into
the upstream-source denominator. Source-only runs are separate from timed
measurements.

The SP3 typed-pool, field-interior and stack/global registration APIs are
covered by runtime PoC tests. Existing real application boundaries use their
actual checked heap metadata and copy/tokenize nonheap trusted pointers.
Successful tests therefore **do not** establish that every production boundary
uses the newer nonheap check APIs.

Each collector writes a `publication_ready: false` marker. That marker stays
false until human review of host configuration, binary provenance, complete
raw samples, load-generator capacity, outliers and repeatability. All failures
and retries must be preserved. Archive downloaded CI artifacts outside GitHub
before their 90-day retention expires.

Related: `CONTROLLED_EVALUATION.md`, `EVALUATION_COMPLETION.md`,
and the archived hosted-reference audit. The original ZIP/libzip
source-performance row remains unverified and must not be fabricated.
