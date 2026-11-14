# Ordinary-only memcached profile on the VM

## Result and scope

The distinct corrected v2 attempt passed independent saved-evidence verification.
The tested application source is `708ceb73c8b048966b9c2becfeaabca2c3b0769e`,
not the evolving branch head. Both native and diagnostic binaries were built
fresh from that clean source. All execution was on the authorized VM.

- Native and diagnostics each passed the existing 16 ordinary functional checks.
- Each retained 34 connection transcripts containing 9,542 read/write events.
- The single diagnostic `balanced_1c` profile completed 5,000 operations:
  2,503 GETs, all hits, and 2,497 SETs. Client errors, misses, worker-log drops,
  watcher skips and LRU-bump drops were all zero.
- The independently recounted 3,322-line trace contains 616 runtime checks
  (306 request, 306 push, two peek_all, two poll), 1,160 sandbox calls,
  4,896 bytes copied into U, 9,792 from U, and 306 LRU holds and takes.
- These counts describe this one ordinary run. They are not a performance
  estimate, a complete workload characterization, or evidence of policy efficacy.

The original 50-case gate was not run or modified. No injection selector or
fault case was executed. This is not security, timing, latency, capacity or
comparative-performance validation and does not complete F1 or the evaluation.
The diagnostic binary contains the standard compiled fault hooks, but none was
enabled. No hosted workflow, merge, tag or paper change was performed for this run.

## Protocol and outcomes, with no omitted attempts

The normal-only protocol is separate from the repaired production workflow.
It directly calls the source's `normal()` function on native and diagnostic
servers and uses the unchanged collector's `collect_one` and verifier's
`verify_attempt` for the profile. It does not call the original prepare/gate
acceptance path and cannot be substituted for a 50-case gate pass.

1. Initial v1 attempt, plan SHA256
   `d9ec81e30f0edd4e56810c4c71c371dfb5f147eafc7292254f4ef2ca5e6ea2df`:
   retained as `normal_failed`. Native `normal()` completed and returned its
   full check inventory, but the wrapper incorrectly required shutdown exit
   -15 and rejected clean exit 0. Diagnostics and profile never started.
   The original failed ledger, exception, plan, transcripts and protocol remain
   unchanged. This attempt is not relabeled as a pass.
2. The documented prospective v2 amendment accepts only integer exit 0 or -15,
   matching pinned memcached SIGTERM handling and the unchanged profile verifier.
   It also records completed normal checks before the shutdown check. Independent
   review confirmed unchanged binaries, source, workload, sample size and
   correctness rules before the new attempt began.
3. Distinct v2 attempt, plan SHA256
   `d3612af1f97d29896faf359be24c5e57384e7738391b45ae925ae0360d1400d2`:
   collected once and verified successfully. Both normal servers exited 0.
   Eight synthetic protocol tests passed. The independent review reran only
   saved-evidence verification, not application traffic.

The profile uses 2,048 keys, 256-byte values, one client, pipeline 10,
50% GET probability, independent-v1 seed 20261109 and count-only measurement.
An independent workload oracle reconstructs the exact key/verb histogram.
Preload and settling are excluded from the declared trace interval; fixed
traffic, post-traffic settling and drain are included. Incidental raw timings
are not used as results.

Normal wire data are complete for calls through `normal()` but exclude the
server-startup version probes. Saved verification checks their integrity and
the retained watcher records; it does not independently replay every normal
assertion. The profile verifier checks aggregate counters, client result,
expected work and every trace event under the existing strict rules.

## Provenance and setup

- Native binary SHA256: `a95b71019dcafd9d20bf88560e3de3037e1ae6ffa625dd8832614078906b1d4a`
- Diagnostics: `915933b464bdf1e6cde467f761c029380cc95e5d16879dbedb589230cf0cb4d9`
- Client: `4342fa775f468823a5600a615ad9ce3c1d680856100474c4e5420b69504981dd`

The client was compiled from the pinned current source and passed ten ordinary
valid count-only protocol fixtures. Frozen plans hash application and harness
sources, binaries, build recipe, toolchain/dependency provenance and validators.
The executed Python binary and assertion-enabled execution are bound in the plan.
The external ordinary protocol is identified by its frozen source hashes; it is
not claimed to have been present in application commit 708ceb7.

Four build-bootstrap failures preceded the successful fresh build. They involved
locally extracted autotools paths, missing config.guess/config.sub, and the aclocal
macro search path. Their logs remain in the archive. The final setup used official
Debian packages extracted into the workspace, not a system package installation.
The macro failure was not established as an autoconf-version incompatibility.
No application measurements were made during these setup failures.

Pre-traffic provenance corrections and the original generated-bytecode preparation
failure are retained separately. They are not measurement retries. The v1 failure
and the distinct v2 result are both included, not selected from repeated profiles.

## Replay and repository status

The raw-evidence archive includes both complete attempts, frozen executed
binaries, all normal transcripts and profile trace/counters, both protocols,
setup logs, amendments, manifests and independent verification output.
From its extracted root, verify saved v2 evidence without starting applications:

```
python3 harness-v2/verify_ordinary_profile.py --root attempt-v2 --plan attempt-v2/frozen/plan.json
```

The archive manifest records all packaged file hashes. The repository companion
files retain the result, plan, amendment and protocol source; they do not claim
to contain the full raw archive. Shared preexisting toolchain binaries and full
generated build trees are not copied into the archive. Their identities and build
logs are retained; the archive supports saved-evidence replay, not an offline
clean rebuild of every dependency.

At publication preparation, concurrent branch head `fcd72d7` had no changes to
the tested memcached sources, shared InterSpec includes, profile harness, client
or build script relative to 708ceb7. This does not validate its other changes.
The new evidence is published with `[skip ci]` and does not replace another
session's CI evidence. F1 remains open under the repository's current criteria.
