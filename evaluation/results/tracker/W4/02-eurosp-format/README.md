# Paper in the EuroS&P 2027 format, and what is over the page limit

2026-11-19 (PT). Paper branch `claude/nifty-cray-ik99hh` at `ba23a2a`
(`main` is still `dcb2c60`, in the ACM format). Made with the `format-convert`
mode of the `academic-paper` skill, which converts and reports a length
mismatch but does not cut text. JH chose "convert, then propose cuts".

## Requirements (from the call, `eurosp2027-cfp-2026-11-19.txt`)

- LaTeX, A4, the conference's template `eurosp2027-template.zip`
  (`template.sha256`); its class line is
  `\documentclass[compsoc,conference,a4paper,10pt,times]{IEEEtran}`, and its
  `IEEEtran.cls` equals the one already in the paper repository.
- At most 13 pages of body text; references and appendices are not counted,
  and reviewers need not read appendices.
- Registration 25 November 2026, submission 2 December 2026 (AoE).
- Potential harms discussed "within the body of the submission".
- AI-generated content disclosed in the acknowledgments section, naming the
  system and the sections; acknowledgments do not count toward the limit.
- Artifacts on an anonymous service, not GitHub.

## What the conversion changed

Class and options, title block (anonymous author line), keywords, bibliography
style `IEEEtranS`, link colours as in the template; ACM front matter removed.
Needed for a clean build: a smaller column gap in the two performance tables,
the overview figure scaled to the text width, `\appendices` so that appendix
sections are lettered, and `styles/revisions.sty` no longer passes an empty
label to `\bibitem` (citation numbers were blank with a numeric style). Two
sentences that named the ACM CCS policies now say "the conference". No other
text changed.

Build (`build.log.gz`): no errors, no overfull boxes, no undefined references;
23 pages. `paper-clean.tex` builds the same 23 pages.

## Length

`section-lengths.txt`, from `tools/paper_section_lengths.py` (start of each
heading in the PDF, in pages; a section's length includes the figures and
tables placed in it). The body ends at page 17.0: 4.0 pages over.

| Section | Pages |
|---|---:|
| 1 Introduction (with title and abstract: 1.78) | 1.38 |
| 2 Background | 1.35 |
| 3 Related Work | 0.75 |
| 4 Threat Model | 0.28 |
| 5 CIV Taxonomy and Security Policies | 2.37 |
| 6 Policy Inference and Enforcement | 4.57 |
| 7 Evaluation | 5.21 |
| 8 Limitations and Future Work | 0.58 |
| 9 Conclusion | 0.11 |

## Proposed plan (not applied; estimates, for JH to approve)

| Change | Saves about |
|---|---:|
| Move to an appendix: the object registry's internals in 6.3 (records, U and T objects, Table `tab:object_registry`), one summary paragraph stays | 0.8 |
| Move to an appendix: per-policy cost table with its paragraph; two sentences stay | 0.45 |
| Move to an appendix: registry-operation and memory costs; two sentences stay | 0.3 |
| Move to an appendix: details of the measurement method; the estimator and the alignment statement stay | 0.25 |
| Shorten 5 (taxonomy): the 856-word paragraph on values passed from U to T, and the paragraph on uninitialized memory in shared-memory frameworks | 0.7 |
| Shorten 2 and 3 (background, related work) | 0.7 |
| Shorten the SP1/SP2 enforcement text in 6.2 | 0.4 |
| Shorten the introduction | 0.35 |
| Shorten the three PoC narratives in 7.3; the outcome table stays | 0.35 |
| Shorten the coverage text in 7.2 | 0.15 |
| Total | 4.45 |
