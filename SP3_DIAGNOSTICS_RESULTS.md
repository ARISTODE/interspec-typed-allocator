# SP3 experimental results

Report date: 2026-10-02. Tested source commit: `a74810cbdb1e730aac222d6b6d1815c701fc7d42`, based on `333801ecf677d89d49db0503a2a611a69562471d`. The local tested source tree matches the published tree exactly: `f517fc3e4603516fe1b2befbf026a263f9ae35b6`.

## Outcome

* All 20 CTest tests passed, including the new diagnostic metadata and disabled-sink test.
* All 25 existing runtime security CSV cases passed with real allocator/check trace output.
* All 25 application and boundary experiment cases passed after fixing a functional defect discovered during evaluation.
* All 12 invalid pointer injections across three actual rsync bridge paths were rejected. Each had a matching trusted rejection, no successful copy of the corrupted pointer after injection, SIGABRT termination, and an untouched destination directory.
* All three valid same type substitutions were accepted and the transfer contents matched expectations. This is the expected limit of the allocation checks.
* The copyback test preserved the intended T destination and surrounding guards after U redirected its option destination. The synchronization regression preserved both an integer update and a string content update made by T between parser calls.

These suite counts overlap in the properties they exercise. They are not a count of independent security guarantees. The tests demonstrate the recorded cases rather than exhaustive correctness or a proof.

## A functional defect was found and fixed

Before the fix, the 24-case matrix passed 17 cases and failed seven. rsync returned exit code 0 for an archive transfer but printed:

```text
skipping directory .
```

The protected destination remained empty. The update/delete workload reported that deletion required recursion. The bridge had copied stale U shadow values back over flags that T set when interpreting `-a`.

The fix retains previous synchronized values privately in T and refreshes changed U shadows before the next parser call. It compares string contents as well as nullness, so an in-place T string change is detected. Destination addresses remain private, trusted bindings. The original failing summary and representative logs are included in the evidence archive under `before-sync-fix/`.

This finding changes the progress assessment: the old version/dry-run smoke alone was insufficient evidence for correct application deployment. The new file transfer comparisons supply stronger evidence for the tested rsync workloads. The functional change also requires fresh performance evaluation with tracing disabled.

## Normal operations

The native reference and protected executable use the same rsync source revision, `7c20b077c980036a19587701cec320cc88e42a4a`. The native reference uses its original bundled popt; the protected executable runs the transformed bundled popt inside RLBox wasm2c. Neither executable uses a check bypass in these experiments.

The initial dataset has seven regular-file paths, two directories, and one symbolic link. Its regular-file path sizes total 2,359,410 bytes, counting both hard-link names. It includes an empty file, binary content, a file larger than 1 MiB, nested and empty directories, executable permissions, a Unicode filename, hard links, and a symbolic link.

| Workload | Observed result |
| --- | --- |
| Archive transfer with checksum and block-size options | Both exited 0; all 10 destination entries matched expected metadata and content |
| Maximum size filter of 1 MiB | Both exited 0; six regular-file paths remained, and the 2 MiB file was excluded |
| Dry run with itemized changes | Both exited 0; output matched and destinations remained empty |
| Update, delete, and backup | Both exited 0; destination manifests matched the changed source; backup manifests matched with three entries |
| Invalid numeric option | Both returned ordinary application error 1; no SP3 rejection |
| Unknown option | Both returned ordinary application error 1; no SP3 rejection |

The comparisons include SHA-256, file size, file permissions, owner/group IDs, file modification timestamps, symlink targets, and hard-link groups. Directory and symlink timestamps, ACLs, xattrs, remote transports, config aliases, and the complete rsync option space are not evaluated. Test input directories are temporary; their manifests and exact commands are retained.

## Allocator observations

| Workload | Successful typed allocations | Requested allocation bytes | Checked strings copied |
| --- | ---: | ---: | ---: |
| `archive_transfer-integrated` | 269 | 3299 | 7 |
| `size_filter-integrated` | 274 | 3320 | 10 |
| `update_backup-integrated` | 272 | 3506 | 6 |

These are events in the captured runs, not total application malloc counts, resident memory usage, or performance measurements. The byte totals exclude allocator alignment, the reserved 16 MiB arena, and allocations outside typed tracking.

For this generated popt policy:

| Type/site | Meaning |
| --- | --- |
| Type hash `0xcc56e9e` | `char` |
| Type hash `0xf967e4189a75ffa` | `poptContext_s` |
| Site 1 | Character allocation in `expandNextArg` |
| Site 2 | Context allocation in `poptGetContext` |
| Site 3 | Existing typed string helper |

Numeric allocator pointers below are wasm sandbox offsets. `runtime` identifies a host-side metadata object. PID and host addresses vary across runs.

## Actual rejection records

The following are verbatim selected lines from the final run, not illustrative messages. The archive retains complete stdout and stderr for every command.

### Wrong type at the option-return path

```text
INTERSPEC seq=264 pid=35 runtime=0x55ad4477ffd0 thread=12499954355133146730 event=allocate_from_site ptr=0x1023e8 base=0x1023e8 size=412 site=2 actual_type=0xf967e4189a75ffa expected_type=0x0 requested=412 offset=0 remaining=412 replacement=0x0 result=ok
FAULT_INJECTION mode=1 target=1 original=0x102590 replacement=0x1023e8
INTERSPEC seq=274 pid=35 runtime=0x55ad4477ffd0 thread=12499954355133146730 event=remaining_bytes ptr=0x1023e8 base=0x1023e8 size=412 site=2 actual_type=0xf967e4189a75ffa expected_type=0xcc56e9e requested=0 offset=0 remaining=412 replacement=0x0 result=wrong_type
INTERSPEC_REJECT reason=InterSpec rejected popt char pointer: wrong_type
```

The substituted pointer belongs to a live tracked 412-byte context object. The mismatch is between its recorded context type and the character type expected by T.

### Freed pointer at the option-return path

```text
INTERSPEC seq=274 pid=37 runtime=0x5572d0e97fd0 thread=13521320155411433699 event=release ptr=0x102590 base=0x102590 size=5 site=1 actual_type=0xcc56e9e expected_type=0x0 requested=0 offset=0 remaining=5 replacement=0x0 result=ok
FAULT_INJECTION mode=3 target=1 original=0x102590 replacement=0x102590
INTERSPEC seq=275 pid=37 runtime=0x5572d0e97fd0 thread=13521320155411433699 event=remaining_bytes ptr=0x102590 base=0x0 size=0 site=0 actual_type=0x0 expected_type=0xcc56e9e requested=0 offset=0 remaining=0 replacement=0x0 result=untracked
INTERSPEC_REJECT reason=InterSpec rejected popt char pointer: untracked
```

The successful release removes the allocation record. Returning that same pointer then produces `untracked`. An ordinary U malloc substitution produces the same check result, but has no preceding tracked release; the lifecycle trace distinguishes these test histories.

### Unterminated string

```text
INTERSPEC_REJECT reason=InterSpec rejected unterminated popt string
```

The allocation/type check accepts a live character allocation, then the wrapper's bounded terminator search rejects the modified contents before copying. This is a wrapper rejection, not `Runtime::check()` returning `out_of_bounds`.

### Excessive extent in the real wasm boundary smoke

```text
INTERSPEC seq=3 pid=59 runtime=0x563a91423420 thread=4573029075315455200 event=check ptr=0x1015b0 base=0x1015b0 size=4 site=3 actual_type=0xcc56e9e expected_type=0xcc56e9e requested=5 offset=0 remaining=4 replacement=0x0 result=out_of_bounds
```

The driver requested five bytes from a four-byte tracked allocation. This is a real sandbox allocation checked by the runtime, but it is not a complete rsync application extent attack; the rsync string interface does not take a U-provided byte length.

## Complete application matrix

Targets 1, 2, and 3 are the actual option return (`poptGetOptArg`), string slot copyback, and positional argument paths. Modes 1 through 5 respectively substitute wrong type, ordinary untracked allocation, freed allocation, unterminated content, and another valid allocation of the same type. Mode 6 corrupts U's option destination pointers.

| Experiment | Result | Evidence |
| --- | --- | --- |
| `archive_transfer` | PASS | returncodes={'native': 0, 'integrated': 0}; entries=10; regular_files=7 |
| `size_filter` | PASS | returncodes={'native': 0, 'integrated': 0}; entries=9; regular_files=6 |
| `dry_run` | PASS | returncodes={'native': 0, 'integrated': 0}; entries=0; regular_files=0 |
| `update_delete_backup` | PASS | returncodes={'native': 0, 'integrated': 0}; backup_entries=3 |
| `invalid_numeric_option` | PASS | returncodes={'native': 1, 'integrated': 1} |
| `unknown_option` | PASS | returncodes={'native': 1, 'integrated': 1} |
| `fault-target1-mode1` | PASS | expected=wrong_type; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=False |
| `fault-target1-mode2` | PASS | expected=untracked; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=False |
| `fault-target1-mode3` | PASS | expected=untracked; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=True |
| `fault-target1-mode4` | PASS | expected=unterminated_string; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=False |
| `fault-target1-mode5` | PASS | expected=copied; returncode=0; injection_reached=True; matching_trusted_decision=True; copied=True; prior_release=False |
| `fault-target2-mode1` | PASS | expected=wrong_type; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=False |
| `fault-target2-mode2` | PASS | expected=untracked; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=False |
| `fault-target2-mode3` | PASS | expected=untracked; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=True |
| `fault-target2-mode4` | PASS | expected=unterminated_string; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=False |
| `fault-target2-mode5` | PASS | expected=copied; returncode=0; injection_reached=True; matching_trusted_decision=True; copied=True; prior_release=False |
| `fault-target3-mode1` | PASS | expected=wrong_type; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=False |
| `fault-target3-mode2` | PASS | expected=untracked; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=False |
| `fault-target3-mode3` | PASS | expected=untracked; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=True |
| `fault-target3-mode4` | PASS | expected=unterminated_string; returncode=-6; injection_reached=True; matching_trusted_decision=True; copied=False; prior_release=False |
| `fault-target3-mode5` | PASS | expected=copied; returncode=0; injection_reached=True; matching_trusted_decision=True; copied=True; prior_release=False |
| `copyback-mode0` | PASS | returncode=0; fixed_destination=True; stdout=copyback_canary=pass destination_value=expected guards_unchanged=true |
| `copyback-mode6` | PASS | returncode=0; fixed_destination=True; stdout=copyback_canary=pass destination_value=expected guards_unchanged=true |
| `shadow_refresh` | PASS | returncode=0; stdout=shadow_refresh=pass counter=99 text=First |
| `wasm_boundary_smoke` | PASS | returncode=0 |

For mode 5, content is deliberately preserved while object identity changes. Acceptance demonstrates the absence of identity binding; it does not demonstrate malicious semantic content being accepted by every application operation.

## Additional library boundaries

All three real library boundary drivers passed in a fresh RLBox wasm2c build. The runtime emitted 15 pointer checks: six `ok`, three `wrong_type`, three `untracked`, and three `out_of_bounds`. The additional foreign-site allocation attempt returned null and left the memcached policy's allocation table empty.

| Boundary | Valid checks | Wrong type | Untracked | Excessive extent observed |
| --- | --- | --- | --- | --- |
| bipbuffer | 2 accepted | Rejected | Rejected | Requested 1,044 bytes, with 64 remaining |
| PCRE | 2 accepted | Rejected | Rejected | Requested 4,103 bytes, with 28 remaining |
| libyaml | 2 accepted | Rejected | Rejected | Requested 4,110 bytes, with 15 remaining |

Actual driver stdout:

```text
boundary=bipbuffer valid=ok wrong_type=wrong_type untracked=untracked oversized=out_of_bounds foreign_site=rejected result=pass
boundary=pcre valid=ok wrong_type=wrong_type untracked=untracked oversized=out_of_bounds result=pass
boundary=yaml valid=ok wrong_type=wrong_type untracked=untracked oversized=out_of_bounds result=pass
```

Allocation snapshots and full check records are included in `p7c.stderr` in the evidence archive. These exercise bipbuffer operations, compiled regex metadata, and scalar event output from the real libraries. They do not run a complete memcached or nginx server, or a complete YAML application. [Machine-readable boundary results](evaluation/results/sp3-diagnostics/p7c-summary.json).


## Reproduction and evidence

[SP3_DIAGNOSTICS.md](SP3_DIAGNOSTICS.md) describes the instrumentation, fault selectors, and reproduction commands. The evidence files are:

* [Machine-readable application results](evaluation/results/sp3-diagnostics/summary.json): every case, command, return code, event counts, and binary SHA-256.
* [Runtime security cases](evaluation/results/sp3-diagnostics/security.csv): all 25 expectations and actual results.
* [Environment](evaluation/results/sp3-diagnostics/environment.json): compiler/platform information, source tree, dependency commits, and policy fingerprint.
* [Complete raw evidence](evaluation/results/sp3-diagnostics/evidence.tar.gz): build logs, CTest output, stdout/stderr, file manifests, generated policy, allocation dump, and the earlier failing evidence.

The executor's own timestamps and process identifiers are recorded in the raw evidence. The reviewed source is pinned independently by commit/tree hashes. No controlled performance numbers are reported from these traced runs.

## Remaining claims and next work

| Claim | Current evidence | Remaining work |
| --- | --- | --- |
| Selected rsync operations preserve behavior | Native/protected file and error comparisons passed | Broader option/configuration coverage, network transfers, upstream test suite |
| Corrupted pointers are rejected on application paths | Twelve actual rsync path injections rejected as expected | More application APIs, buffer/length application paths, additional misuse combinations |
| T copyback destination is preserved | Exact bridge canary and private binding trace passed | Additional destination kinds and applications |
| Reuse across library boundaries | Additional driver results reported above | Complete memcached, nginx, and YAML application deployment and output validation |
| Allocator temporal behavior | Release/reallocation tests reject retired addresses | Long-running allocation growth and capacity tests; address reuse design if required |
| Concurrent U mutation is safe | Not established by these experiments | An explicit synchronization/snapshot design and adversarial concurrency evaluation |
| Same type object identity and semantic correctness | Same type substitutions accepted as expected | Per-operation object binding or application validation if these are required claims |
| Low deployment overhead | Existing performance machinery remains available | Rerun native/RLBox/tracking/full comparisons after the synchronization fix, with diagnostics and fault hooks disabled |

The changes are on a review branch, not merged into main. GitHub CI is a separate verification run; its status should be checked on the pull request rather than inferred from the local results.
