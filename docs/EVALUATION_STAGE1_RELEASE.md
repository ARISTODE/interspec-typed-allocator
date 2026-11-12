# Stage 1 technical release: corrected client and recovery primitive

This release is a locally tracked, tested continuation of 6e164d3a62db94e4774345ee32f7d03cf3906bce. It does not change server enforcement code or the paper. No push, performance matrix, or new controlled-host experiment was performed.

## Changes

- Includes the 2026-11-09 independent-v1 key/type correction, count-only throughput and bounded sampled-latency implementation.
- Rejects malformed numeric arguments, nonfinite/over-one-day durations, invalid ports, signed unsigned arguments, and fixed-work ticket-counter wraparound. Invalid arguments return status 2 rather than an uncaught conversion exception. Uses size_t for buffer-reservation arithmetic.
- Registers the actual benchmark client and functional protocol regression in CMake. A loopback ASCII fixture checks six mode/concurrency cases, exact independently calculated GET/SET counts, sample selection, overflow null quantiles, corrupt-response rejection and ten invalid-argument cases. This fixture is not memcached and supplies no performance evidence.
- The deployment renderer rejects mixed generator modes/seeds and environment mismatches, labels generator/seed, and preserves legacy interpretation for historical missing metadata. Seven new renderer cases are included.
- Adds a local, hash-checked, atomic/fsync checkpoint ledger and ten standalone tests including actual SIGKILL transitions. It neither launches experiments nor uploads files. The existing collectors are not integrated with it.
- Adds an explicit A/A/headroom protocol proposal and recovery contract. Proposed margins, sessions, counts and physical-core requirements are not represented as user-agreed or satisfied.

## Verification on this workspace

Release and Debug configurations: 32/32 CTest passed in each. Debug retains assertions. C++17 strict build of the client uses -O2 -pthread -Wall -Wextra -Wpedantic -Werror and passes the protocol fixture. Python modules compile; git diff --check passes. Test logs and exact compiler/CMake/Python versions are included in the release evidence. A workspace-local CMake 4.4.4 package was used because CMake was initially unavailable.

Tests are functional checks, not a claim of exhaustive correctness, real-server validation of this final binary, dedicated-host measurements or statistical equivalence. The older report records seven real-server cases for its older binary; those are historical evidence, not a fresh run of this release.

## Remaining gates, in order

1. Agree and freeze the scientific tolerance and confirmatory plan. The proposal uses 2% equivalence and 12 sessions, but no confirmatory schedule can be frozen until pilot operation counts and a suitable host are known.
2. Verify host control/exclusivity and placement. The authorized VM remains reference-only; provisioning a new host is not authorized by this release.
3. Integrate the ledger with the real driver and remote destination, then exercise end-to-end crash/restoration and uncertain-upload handling. Local kill tests do not close this gate.
4. Repeat real-server correctness with the final client and exact server binaries, then run the frozen A/A and added-resource gate. Keep exploratory pilot data separate.
5. Only after all relevant gates pass, launch a separately frozen four-variant/six-scenario matrix. Discuss interpretation with the user before editing the paper evaluation.

The prior VM experiment's A/A variability and inconclusive headroom remain unresolved. There is no evidence here that negative overhead bars are a genuine optimization.
