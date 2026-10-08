# Nginx application reference evidence

`correctness-summary.json` records the executed application and corruption cases.
`build-manifest.json` records tested binary and generated-source hashes.
`collection-provenance.json` binds the local build source to the implementation commit and records the exact measurement driver and wrk revision.
`core-tests.log` records the 20 passing core regressions.

The complete reference includes five paired repetitions for each of the 4 and 8 wrk thread settings, 100 connections, and 30-second measurement windows. Raw HTTP checks, logs, and wrk outputs are retained in the evidence archive with its SHA-256 manifest.

This is shared-environment reference evidence. CPU/RSS counters unavailable in the local PID namespace remain missing. Multiple-worker and reload validation and a clean remote CI build remain pending approval to publish the branch. Controlled-hardware publication measurements remain separate.

`validation-20261008/` records a subsequent fresh run of the complete build
script at `1b8cbc6`, followed by 22 passing application cases. Its binaries and
logs are separate from the original timing evidence. The saved native worker
startup log records the local `initgroups` permission failure; worker/reload
validation still requires CI. No new performance numbers were collected.
