# A1: reuse of released addresses in the typed allocator

Not a tracker row: JH decided this change on 2026-11-14 (see the Log of
`EVAL_TRACKER.md`), after the ucl/libucl port ran out of arena
(`evaluation/results/tracker/I11/03-arena-exhaustion-before-reuse-0972491/`).

## The rule

`include/interspec/runtime.h`: a released arena block is kept in a list for
its allocation site (and type). A later allocation at the same site takes the
smallest kept block that is large enough and has the required alignment;
otherwise it takes fresh arena as before. No other site is ever given the
address. The record of the new object carries the new size, so the bounds of
a check are those of the new object. While a block is released, no record
covers it and a check reports `untracked`.

What this changes for SP3: a pointer to a released object used to match no
later record. Now it can match a later object allocated at the same site, of
the same type, if the access fits the new object's size. It still cannot
match an object of another site or type.

## Evidence

| Directory | Commit | Result |
|---|---|---|
| `01-test-before-change-ae58f4e/` | test only | `tests/runtime_address_reuse.cpp` against the unchanged allocator: 8 checks fail. A loop of allocate and release in a 4 KiB arena stops after 34 steps. |
| `02-change-62cd9c7/` | `62cd9c7` | From a clean checkout: the whole unit-test suite (40 tests) passes, and the new test passes: one million allocate and release steps in a 4 KiB arena, 100,000 rounds of growth by reallocation. |

In `02-change-62cd9c7/` the absolute paths of the scratch checkout and build
directory in the three log files were replaced by `<checkout>` and `<build>`;
nothing else in the logs was edited.

One existing test changed with the allocator: the concurrent loop in
`tests/runtime_hardening.cpp` asserted that a released address stays
unrecorded. With eight threads allocating at the same site that no longer
holds, and the assertion was removed there; the new test asserts it without
concurrency.

## What was rerun

- The ucl/libucl and magick/libpng shims went back to one allocation per call
  (`9f803c0`), which is what first exposed the limit. Reruns from a clean
  checkout, including long runs in all three isolated variants:
  `evaluation/results/tracker/I11/05-allocator-reuse-9f803c0/` (200,000 parses)
  and `evaluation/results/tracker/I8/03-allocator-reuse-9f803c0/` (50,000
  decode and encode rounds).
- Every boundary's switch tests and benign run, and the deployment workflows,
  rerun on CI at the commit that records this README; the tracker rows name
  that run.
