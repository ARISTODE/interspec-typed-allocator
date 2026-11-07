# Extended SP3 security-delta evaluation plan

**Status:** plan and pre-registered predictions. No result in this file is an
observation. Results will be recorded separately and must not overwrite the
predictions below.

## 1. Question

The existing negative tests show that Extended SP3 *rejects* malformed U
pointers. They do not show that *accepting* such a pointer would harm T. The
question this plan answers is:

> For which pointer classes does Extended SP3 change T's observable outcome
> compared with the paper's domain-only SP3 and with RLBox plus the existing
> bridge validation?

## 2. Two hypotheses

**H1 (U-domain pointers).** For pointers whose expected domain is U memory,
Extended SP3 does not change T's observable outcome compared with RLBox-only
plus the existing bridge validation.

Reasoning from the current code:

* U chooses each tracked allocation's size (wasm allocation imports take only
  a size, `tools/generate_wasm_boundary_policy.py:157,300`) and its lifetime
  (U invokes release, `:308`).
* The typed arena lies in U linear memory, so U controls every byte in it.
* Every evaluated bridge confines the pointer to sandbox memory, copies a
  T-capped length, and then validates the copied content
  (memcached `bridge.cpp` `validate`/`snapshot`; nginx `bridge.cpp:186-217`;
  rsync `p4c_bridge.cpp:168-190`; yaml `yaml_app_bench.cpp:177-191`).

**H2 (T-domain pointers).** For pointers whose expected domain is T memory,
the paper's domain check (accept any address outside sandbox memory,
`policy_inference_and_impl.tex` SP3 enforcement paragraph) does not establish
that the pointer refers to the intended live T object of the expected type.
An object-level check against T-registered objects does.

Original-source T-domain transits identified so far:

| Boundary | Pointer | Original source | Current bridge |
| --- | --- | --- | --- |
| memcached/bipbuffer | LRU bump entry item pointer | `items.c` at `2d51e36` | replaced by one-use integer handles (`tools/prepare_memcached_deployment.py:41-45`) |
| yaml/libyaml | read-handler `data` context | `yaml_parser_set_input` API | not exercised by the project driver |
| nginx/openssl | `ex_data_ptr` (paper's running example) | OpenSSL `ex_data` | no wasm2c build in this repository |

## 3. Configurations compared

| Configuration | U-domain check | T-domain check |
| --- | --- | --- |
| `rlbox_only` | sandbox confinement + bridge capacity/content validation | none beyond the bridge |
| `domain_sp3` | inside sandbox memory | outside sandbox memory (paper SP3) |
| `extended_sp3` | live tracked allocation, expected type, extent | live T-registered object, expected type, revoked after use |

The existing `tracked_no_check` binary is a performance baseline that
deliberately trusts known-valid input. It is **not** a security comparator.

## 4. Outcome measures

For every run, record what T observably does, not only whether a check fired:

1. T process exit status and any sanitizer report in T;
2. T's externally visible output (protocol responses, stdout, files written);
3. the existing 50-case memcached correctness gate rerun after the case;
4. the boundary check decision and its census record.

**Decision rule for H1.** A test case shows *no security delta* when
`rlbox_only` yields no sanitizer report and no T-visible outcome that differs
from what a legitimate pointer with U-chosen contents produces.

**Decision rule for H2.** A case shows a *security delta* when `domain_sp3`
accepts the pointer and T's outcome differs from the legitimate case, while
`extended_sp3` rejects it before T uses the value.

## 5. Pre-registered predictions

### H1, existing memcached fault modes (`integration/memcached_server/bipbuffer_u.c`)

| Mode | Description | `extended_sp3` (already observed in CI) | `rlbox_only` predicted |
| --- | --- | --- | --- |
| 1 | live char allocation, wrong type | rejected `wrong_type` | no T harm |
| 2 | untracked U heap storage | rejected `untracked` | no T harm |
| 3 | released owner metadata | rejected `untracked` | no T harm |
| 4 | extent past the tracked object | rejected `out_of_bounds` | no T harm; bridge capacity check still bounds the copy |
| 5 | same-type substitution | accepted (documented scope limit) | accepted |
| 6 | malformed record contents | rejected by T's format validator | rejected by T's format validator |
| 7 | corrupted hash next to an LRU handle | rejected by handle validation | rejected by handle validation |
| 8 | in-bounds extent splitting an LRU record | rejected by `interspec_lru_extent` | rejected by `interspec_lru_extent` |
| 9 | U static-duration object | rejected `untracked` | no T harm |
| 10 | escaped U stack address | rejected `untracked` | no T harm |

"No T harm" means: no sanitizer report, T keeps serving, the correctness gate
still passes, and any T-visible difference is reproducible by U writing the
same bytes behind the legitimate pointer.

### H2

| Pointer | `rlbox_only` / `domain_sp3` predicted | `extended_sp3` predicted |
| --- | --- | --- |
| memcached LRU item pointer, upstream form | accepted for any non-sandbox address | rejected unless it is a live, registered item whose registration has not yet been consumed |
| libyaml read-handler `data` | accepted for any non-sandbox address | rejected unless it is the registered context object of the expected type |

If H1 fails for any case, that case becomes positive evidence for Extended
SP3 on U-domain pointers and the current claim stands for it. If H2 holds but
manual handles (as in the current memcached bridge) are equally safe, the
contribution is automation of that protection rather than a new guarantee.

## 6. Scope and execution environment

* Builds, correctness gates and security runs execute on the 4-vCPU cloud VM
  and in GitHub Actions. They do not depend on dedicated hardware.
* Timing is out of scope here; it belongs to the controlled evaluation.
* The paper repository is not modified. Claim text in this repository is
  updated only after results are recorded and reviewed.
