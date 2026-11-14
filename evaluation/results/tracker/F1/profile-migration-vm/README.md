# F1 current-source profile migration: focused VM validation

The compatibility fix `81d4785` and every concurrent change through `f904ae6`
are retained. The two workflow call sites now use the frozen v2 wrapper described
in [the protocol](../../../../../docs/MEMCACHED_PROFILE_WORKFLOW.md). The older
`profile_memcached_checks_hosted.py` file is unchanged. No merge to main or tag was made.

The local VM code commit in `source-commit.txt` passed 17 current-profile contract tests,
39 corrected-profile tests, ten legacy-profile tests and 12 metadata/renderer
cases on the available VM. The current-profile suite compiles a current client
and checks ten valid-response count-only loopback fixtures (926 responses),
then exercises a synthetic six-scenario evidence replay, export and renderer.
It never launches an actual memcached diagnostic server. The synthetic gate is
a test fixture, not evidence of a new real 50-case gate.

The local commit is a tested identity, not a separately published GitHub commit.
All 11 source identities are recorded in `source-sha256.json`; they are
unchanged in the published migration despite the intervening tracker/nginx merge. Raw test-process
stdout and stderr are retained alongside `COMMANDS.md` and `status.txt`.
Independent source review accepted the migration and its final path-override
fix. The original v1 revision and binary pins remain unchanged; this is not an
upgrade or reinterpretation of historical evidence.

**F1 remains doing.** These focused tests are not a successful complete workflow
run, a new actual profile, a timing result, or completion of the evaluation.
No hosted workflow was dispatched. Publication uses `[skip ci]` to respect the
VM-only direction. Failed runs 43393783638 and 43393791474 remain historical
failures; this patch does not change their status.
