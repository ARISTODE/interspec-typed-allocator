# P9c Paper SP3 Coverage Reconciliation

P9c answers a paper facing evaluation question: among the 32 pointer fields protected by SP3 in the final InterSpec evaluation, which cases can the Extended SP3 typed allocator strengthen from pointee domain integrity to trusted allocation liveness, expected type, and spatial containment?

P9c adds no new enforcement mechanism. Its purpose is to make the coverage claim auditable and to prevent a stronger Extended SP3 claim from being inferred from boundary demonstrations alone.

## 1. Coverage unit

The final InterSpec paper evaluates SP3 at interface field granularity. Section 7.2 reports 32 pointer fields protected by SP3 across 10 boundaries. P9c therefore uses one paper SP3 pointer field as the coverage unit.

The pinned source of truth is:

```text
repository: ARISTODE/interspec-artifact
commit: 2b2d2fd4de69ee44a4363e69f8cfb82ceed132db
table: data/processed/paper/integrity_coverage.csv
blob: 5c5f0e9b4b4a5b548504653680d0cf158d2db613
paper source commit: c692d9581e17689ca1dc20545c48a355c6a86ff6
```

P9c vendors that processed table unchanged at `evaluation/p9c/interspec_paper_integrity_coverage.csv`. The evaluator requires the per boundary SP3 counts and the total of 32 to match the P9c manifest exactly.

## 2. Why raw SP3 reports are not treated as the 32 paper cases

The packaged InterSpec artifact preserves the final paper counts, but it does not preserve a declared one row per paper field identity map for all 32 fields. The raw `sp3_cases.csv` reports were produced through report paths whose granularity and semantics are not consistently identical to the final paper table.

This is observable in the artifact itself. The final paper table counts 3 SP3 fields for magick/libpng while the packaged raw case file contains 2 rows. The final paper counts 2 fields for ffmpeg/libvpx while the main raw report does not contain a paper aligned two row case list. nginx/OpenSSL contains many raw path level candidates while the final table counts 5 SP3 fields and 11 unknown expected domain fields. The artifact's generated pointer report also excludes nginx/OpenSSL and reports 53 SP3 path level cases across the remaining nine boundaries, which is a different analysis unit from the final paper's 32 fields.

Equal cardinality is not sufficient proof of identity. A raw report row is not assigned to a paper field unless preserved source evidence explicitly binds them. P9c therefore does not synthesize field names or silently substitute a different raw analysis for the final paper coverage units.

## 3. Stable paper case identifiers

`tools/build_p9c_report.py` expands the 10 paper table counts into exactly 32 stable identifiers such as:

```text
rsync_popt_sp3_01
rsync_popt_sp3_02
...
```

These identifiers denote count units only. They are not claims about original source field names.

Every generated case receives explicit fields for identity status, Extended SP3 capability status, prototype status, source basis, and notes. An unresolved case therefore remains visible in the denominator instead of disappearing from the result.

## 4. Capability classification

A paper case may receive one of three capability states.

1. `eligible` means source evidence reconstructs the paper field identity and establishes the information required by the current Extended SP3 model: a U controlled pointer consumed by T, a trusted allocation identity for the relevant U allocation, an expected allocation type, and a trusted use extent that can be checked against the allocation.

2. `ineligible` means the reconstructed case is outside the current mechanism model. For example, a case whose expected pointee is T memory is outside the evaluated typed allocator when the allocator tracks only U allocations, unless a separate trusted T allocation mechanism is added.

3. `insufficient_source_metadata` means the final paper count is preserved but the evidence required to classify that exact field is not recoverable from the preserved source snapshot. This state is deliberately distinct from ineligible.

A case is never promoted to eligible merely because its boundary has an Extended SP3 prototype.

## 5. Prototype status

Prototype evidence is tracked separately from capability.

`demonstrated` requires an exact mapping from a reconstructed paper field to a trusted use exercised by the prototype. `not_demonstrated` means no such prototype mapping is claimed. `unresolved_mapping` means the boundary has relevant Extended SP3 mechanism evidence, but the preserved artifact does not prove that the demonstrated trusted use is the same field counted by the final paper.

The repository records mechanism evidence for rsync/popt, memcached/bipbuffer, nginx/libpcre, and yaml/libyaml. P9c intentionally does not count those boundaries wholesale as demonstrated paper coverage.

The paper additionally names concrete rsync/popt and nginx/libpcre SP3 examples that correspond to pointer shapes demonstrated by the prototype. They are recorded as semantic corroboration in `source_reconstruction_audit.json`, but they are not promoted to exact paper case mappings because the preserved source snapshots do not establish the required one to one identity binding.

## 6. Source reconstruction audit

`evaluation/p9c/source_reconstruction_audit.json` records the evidence examined while attempting to recover the 32 identities. It covers the final processed table, the paper reproduction script, the paper claim mapping, the generated raw pointer report, representative raw case cardinality mismatches, the nginx/OpenSSL provenance audit, and the historical paper source listing commit.

The audit conclusion is `source_fidelity_limitation`: the exact one row per paper field map is not recoverable from the preserved final paper artifact. This is not evidence that Extended SP3 is inapplicable. It means a precise case level applicability fraction cannot be derived without inventing identities.

The only defensible case level numerical result is therefore a provenance lower bound. The current exact eligible lower bound is 0 of 32 and the exact demonstrated lower bound is 0 of 32. These zeros are not estimates of actual Extended SP3 applicability.

## 7. Machine readable outputs

Running:

```bash
./scripts/run_p9c_evaluation.sh p9c-results
```

produces:

```text
p9c-report.json
p9c-cases.csv
P9C_RESULTS.md
paper_sp3_manifest.json
source_reconstruction_audit.json
interspec_paper_integrity_coverage.csv
environment.txt
README.txt
```

`p9c-report.json` deliberately separates several questions.

1. `paper_source_integrity` asks whether the pinned table, manifest boundary counts, and total of 32 agree.

2. `classification_explicit` asks whether all 32 paper units have an explicit classification state.

3. `capability_resolution_complete` asks whether every case has been resolved to eligible or ineligible rather than insufficient source metadata.

4. `source_fidelity_complete` asks whether exact paper field identities have been reconstructed for every unit.

5. `source_reconstruction_audit_complete` asks whether the source fidelity limitation is backed by the checked in audit evidence.

6. `p9c_evaluation_complete` is true when either exact capability resolution is complete or the source fidelity limitation is explicitly audited while the paper denominator remains intact.

These booleans must not be collapsed into a claim that all 32 cases were individually classified.

## 8. CI and release gate

The P9c CI job runs the evaluator with `--require-source-integrity` and `--require-complete`. CI fails if the paper denominator changes, a paper unit disappears, a case identifier is duplicated, an invalid classification state is introduced, the reconstruction audit is missing, or the completion state is otherwise inconsistent.

CI does not require `capability_resolution_complete`. Requiring it after the source reconstruction audit established that the preserved artifact lacks the identity map would incentivize unsupported assignments merely to make the build green.

The release package also requires P9c evidence. `scripts/package_release.sh` refuses to create the research archive unless `p9c-report.json` reports `p9c_evaluation_complete=true`, the denominator remains 32, and the generated report, 32 case units, source table, manifest, reconstruction audit, and environment evidence are present. Tagged releases regenerate the P9c evidence before packaging.

## 9. Security claim boundary

Extended SP3 in this repository establishes trusted allocation liveness, expected allocation type, and spatial containment of the requested trusted use extent for covered U allocations.

It does not establish intended object identity among simultaneous same type allocations, temporal identity under physical address reuse, general control flow integrity, or integrity of the object contents. P9c does not count a case as covered by assuming any of these stronger properties.

## 10. Completion result

P9c completes through the second permitted completion path: the final paper denominator of 32 SP3 fields is reproduced exactly, the preserved artifact is shown to be insufficient for reconstructing the exact identity of every field, that limitation is represented in machine readable evidence, and no precise Extended SP3 percentage over the 32 cases is reported.

This conclusion preserves the distinction between two valid forms of evidence. The existing integrations show that the Extended SP3 mechanism works for several real pointer shapes and isolation backends. The P9c paper coverage audit shows that those demonstrations cannot be converted into an exact percentage of the original 32 paper fields from the preserved artifact alone.
