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
```

P9c vendors that processed table unchanged at `evaluation/p9c/interspec_paper_integrity_coverage.csv`. The evaluator requires the per boundary SP3 counts and the total of 32 to match the P9c manifest exactly.

## 2. Why raw SP3 reports are not treated as the 32 paper cases

The packaged InterSpec artifact preserves the final paper counts, but it does not preserve a declared one row per paper field identity map for all 32 fields. The raw `sp3_cases.csv` reports were produced through report paths whose granularity and semantics are not consistently identical to the final paper table.

This is observable in the artifact itself. For example, the final paper table counts 3 SP3 fields for magick/libpng while the packaged raw case file contains 2 rows. The final paper counts 2 fields for ffmpeg/libvpx while the main raw report does not contain a paper aligned two row case list. nginx/OpenSSL contains many raw path level candidates while the final table counts 5 SP3 fields and 11 unknown expected domain fields.

Equal cardinality is also not sufficient proof of identity. A raw report row is not assigned to a paper field unless preserved source evidence explicitly binds them.

P9c therefore does not synthesize field names or silently substitute a newer raw analysis for the final paper coverage units.

## 3. Stable paper case identifiers

`tools/build_p9c_report.py` expands the 10 paper table counts into exactly 32 stable identifiers such as:

```text
rsync_popt_sp3_01
rsync_popt_sp3_02
...
```

These identifiers denote count units only. They are not claims about original source field names.

Every generated case receives explicit fields for identity status, Extended SP3 capability status, prototype status, source basis, and notes. This ensures that an unresolved case is represented as unresolved rather than disappearing from the denominator.

## 4. Capability classification

A paper case may receive one of three capability states.

1. `eligible` means source evidence reconstructs the paper field identity and establishes the information required by the current Extended SP3 model: a U controlled pointer consumed by T, a trusted allocation identity for the relevant U allocation, an expected allocation type, and a trusted use extent that can be checked against the allocation.

2. `ineligible` means the reconstructed case is outside the current mechanism model. An example would be a paper case whose expected pointee is T memory when the evaluated typed allocator tracks only U allocations, unless a separate trusted T allocation mechanism is added.

3. `insufficient_source_metadata` means the final paper count is preserved but the evidence required to classify that exact field has not yet been reconstructed. This state is deliberately distinct from ineligible.

A case is never promoted to eligible merely because its boundary has an Extended SP3 prototype.

## 5. Prototype status

Prototype evidence is tracked separately from capability.

`demonstrated` requires an exact mapping from the reconstructed paper field to a trusted use exercised by the prototype.

`not_demonstrated` means no such prototype mapping is claimed.

`unresolved_mapping` means the boundary has relevant Extended SP3 mechanism evidence, but the preserved artifact does not yet prove that the demonstrated trusted use is the same field counted by the final paper.

The current repository records mechanism evidence for rsync/popt, memcached/bipbuffer, nginx/libpcre, and yaml/libyaml. P9c intentionally does not count those boundaries wholesale as demonstrated paper coverage.

## 6. Machine readable outputs

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
interspec_paper_integrity_coverage.csv
environment.txt
README.txt
```

`p9c-report.json` separates four questions.

1. `paper_source_integrity` asks whether the pinned table, manifest boundary counts, and total of 32 agree.

2. `classification_explicit` asks whether all 32 paper units have an explicit classification state.

3. `capability_resolution_complete` asks whether every case has been resolved to eligible or ineligible rather than insufficient source metadata.

4. `source_fidelity_complete` asks whether exact paper field identities have been reconstructed for every unit.

These booleans must not be collapsed into one completion flag.

## 7. CI gate

The P9c CI job runs the evaluator with `--require-source-integrity`. CI therefore fails if the paper denominator changes, a paper unit disappears, a case identifier is duplicated, an invalid classification state is introduced, or a manifest override references an unknown case.

The current CI gate does not require `capability_resolution_complete`. Doing so would encourage unsupported identity assignments simply to make the build green. A later P9c completion commit may enable `--require-resolved` only after the source reconstruction is actually complete.

## 8. Security claim boundary

Extended SP3 in this repository establishes trusted allocation liveness, expected allocation type, and spatial containment of the requested trusted use extent for covered U allocations.

It does not establish intended object identity among simultaneous same type allocations, temporal identity under physical address reuse, general control flow integrity, or integrity of the object contents. P9c must not count a case as covered by assuming any of these stronger properties.

## 9. P9c completion target

P9c is complete only when either:

1. all 32 exact paper field identities are reconstructed and each is resolved to eligible or ineligible with source evidence, or

2. the paper artifact is shown to be insufficient to reconstruct some identities, that limitation is explicitly reported, and any numerical Extended SP3 paper coverage claim is restricted to a defensible lower bound rather than a guessed exact percentage.

The first implementation step intentionally establishes the source fidelity gate before attempting to increase the resolved count.
