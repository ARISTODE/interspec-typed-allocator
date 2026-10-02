# SP3 diagnostics and application experiments

This experiment observes the trusted allocator and exercises pointer corruption through the real rsync/popt bridge. It does not enable the P8 validation bypass. The test selector changes U's behavior; T's checks and allocation policy stay fixed for each comparison.

## Reproduce

```sh
bash scripts/run_sp3_diagnostics.sh results/sp3-diagnostics
INTERSPEC_DIAGNOSTICS=1 INTERSPEC_TRACE=1 \
  bash scripts/run_p7c_wasm2c.sh >results/sp3-diagnostics/p7c-build.log 2>&1
INTERSPEC_TRACE=1 /tmp/interspec-p7c-wasm2c/p7c-wasm-smoke \
  >results/sp3-diagnostics/p7c.stdout 2>results/sp3-diagnostics/p7c.stderr
```

The scripts use the pinned upstream revisions in the existing backend manifest and integration scripts. Build dependencies include GCC/G++, CMake 3.30 or later, Python 3, Git, autoconf, automake, and libpopt development files. The scripts download the pinned wasi-sdk and build WABT. The native rsync reference is built separately from the same rsync revision with its original bundled popt.

`run_sp3_diagnostics.sh` creates fresh dependency/build directories under `${TMPDIR:-/tmp}`. It captures build output, CTest results, the existing 25-case runtime security CSV, allocator records, and application cases. It exits unsuccessfully if an asserted expectation fails. After a successful build, only the application matrix can be repeated with:

```sh
python3 tools/run_sp3_experiments.py --out results/sp3-repeat
```

## Diagnostics

Compile trusted translation units consistently with `INTERSPEC_ENABLE_TRACE=1`, then set `INTERSPEC_TRACE=1` at process startup. Without the compile flag, the diagnostic sink is absent; with the flag but without that exact environment setting, it emits nothing.

`Runtime` records allocation, release, reallocation, `check`, and `remaining_bytes` decisions. Each record contains its process ID, thread identifier, runtime identity, sequence number, pointer, allocation base, size, allocation site, actual and expected type hashes, requested bytes, offset, remaining extent, replacement pointer, and result. Sequence numbers identify events within a process; concurrent output must not be interpreted as a global transaction ordering.

For wasm2c, allocator pointers are sandbox offsets. `INTERSPEC_BINDING` destination addresses refer to private T memory and use a different address space. The runtime identity is a host address, not a sandbox pointer. Zero metadata fields on an `untracked` event mean no live allocation was found.

Diagnostic records copy scalar metadata under the existing runtime lock, then emit after unlocking. They do not dereference the suspect pointer. `dump_allocations()` copies the live allocation table under a shared lock and prints the snapshot after unlocking. With tracing enabled, setting `INTERSPEC_TRACE_DUMP` also requests a full snapshot when the rsync pointer check rejects. The string wrapper logs whether it copied bytes or rejected the pointer/string; exceptions produce `INTERSPEC_REJECT` before the existing abort behavior.

Some normal frees produce `release result=failed`: popt's allocator shim first asks the typed runtime whether it owns the pointer, then falls back to ordinary free for untracked allocations. This is not itself an SP3 violation. After a successful release, a subsequent stale pointer check reports `untracked`, rather than a special use-after-free status.

## Controlled U faults

Fault injection is compiled only with `INTERSPEC_FAULT_TESTS=1`. The ordinary build has no setter or fault mutation code. Test builds accept numeric `INTERSPEC_TEST_FAULT` and `INTERSPEC_TEST_TARGET` selectors. Faults fire once at the first nonnull pointer on the selected path.

| Mode | U mutation | Expected trusted result |
| --- | --- | --- |
| 0 | No mutation | Normal behavior |
| 1 | Replace character pointer with the live tracked popt context | `wrong_type` |
| 2 | Copy the string into ordinary U malloc memory and return it | `untracked` |
| 3 | Release the tracked allocation and return its old pointer | `untracked`, preceded by successful release |
| 4 | Replace string contents, including its terminator, with nonzero bytes | `unterminated_string` from the wrapper |
| 5 | Return a distinct live character allocation with identical contents | Accepted; object identity is not enforced |
| 6 | Redirect U's option destination pointers to a U decoy after parsing | T still writes only its private prebound destination |

Targets 1, 2, and 3 are respectively `interspec_p4c_opt_arg`, `interspec_p4c_slot_get_string`, and `interspec_p4c_args_at`. These are called by the actual rsync bridge. The test runner uses real transfer commands to reach all three targets, verifies the injected pointer against trusted check records, and requires no successful copy of that pointer after rejection. Rejection cases must end with SIGABRT and leave an initially empty destination untouched. U's injection print is only a test marker; enforcement evidence comes from T's records.

The original legitimate allocation policy is generated before tests, and no new site permission is added for the corruption modes. A malicious test may call existing legitimate allocation/lifetime functions. The same type control deliberately obtains another valid character allocation through the existing typed string helper.

## Normal application behavior

The runner compares protected rsync with a native reference for actual archive transfers, a maximum size filter, dry runs, updates with deletion and backups, malformed numeric options, and unknown options. It records per-file SHA-256 hashes, sizes, permissions, owner/group IDs, file timestamps, symbolic link targets, and hard link groups. The dataset includes an empty file, binary content, a file larger than the size filter, nested and empty directories, an executable, a Unicode filename, a hard link, and a symbolic link.

`copyback_canary.cpp` uses the same compiled bridge and sandboxed popt. It verifies the selected T field and surrounding guards when U rewrites its option destination. A second test changes an integer and string contents inside T between parser calls and verifies that the next call preserves those changes.

## Correctness defect found by these experiments

The original bridge initialized U's shadow option destinations only once. Later, rsync could update T's flags when interpreting an option such as `-a`. The next `poptGetNextOpt()` copied stale shadow values back over those updates. A process could therefore exit successfully while printing `skipping directory .` and transferring no files. The previous `--version` and `--dry-run` exit-status smoke did not detect this.

The bridge now retains the last synchronized values in T and refreshes changed U shadow values before invoking popt. String comparison detects changes to contents even when T keeps the same pointer. The trusted destination binding never comes from U. This fixes the tested behavior and is a functional change whose performance should be measured separately with diagnostics disabled.

## Scope of the evidence

The rsync matrix is an application execution experiment. The separate bipbuffer, PCRE, and libyaml driver uses real libraries inside RLBox wasm2c and captures `ok`, `wrong_type`, `untracked`, and `out_of_bounds` decisions, plus a foreign allocation site rejection. Those results do not establish complete memcached, nginx, or YAML application deployment. The rsync string path does not consume a U-provided byte length; an application-level excessive-length attack needs a buffer/length application path.

These tests do not establish semantic correctness of U's contents, identity of a same-type replacement object, safety against concurrent U mutation between validation and use, complete API coverage, or unbounded service lifetime. The current typed arena does not reuse released addresses. Real deployment also needs allocator capacity/lifetime evaluation and supported configuration/API coverage. This run uses source injection and trusted diagnostics, not eBPF. Logging runs are not performance measurements.
