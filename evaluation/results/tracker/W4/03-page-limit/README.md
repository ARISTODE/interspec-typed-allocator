# Paper body within the 13-page limit of EuroS&P 2027

2026-11-19 (PT). Paper branch `claude/nifty-cray-ik99hh`, commits
`ba23a2a..41d71b8` (`commits.txt`, `diffstat.txt`); `main` is unchanged at
`dcb2c60`. JH approved the plan of `../02-eurosp-format/README.md` ("Nothing,
apply the plan"). Done with the `academic-paper` skill (revision rules: change
only the targeted blocks, no change of a claim's strength, numbers conserved).

## Result

`section-lengths.txt` (from `tools/paper_section_lengths.py`), build log
`build.log.gz`: 21 pages, no errors, no overfull boxes, no undefined
references. The body ends on page 13 (the conclusion starts at 12.86 and takes
about 0.1 page); references start on page 14.

| Section | Before | After |
|---|---:|---:|
| 1 Introduction | 1.38 | 1.19 |
| 2 Background | 1.35 | 0.94 |
| 3 Related Work | 0.75 | 0.65 |
| 4 Threat Model | 0.28 | 0.28 |
| 5 CIV Taxonomy and Security Policies | 2.37 | 1.91 |
| 6 Policy Inference and Enforcement | 4.57 | 3.04 |
| 7 Evaluation | 5.21 | 3.90 |
| 8 Limitations and Future Work | 0.58 | 0.54 |
| 9 Conclusion | 0.11 | 0.15 |
| Body ends at page | 17.0 | 13.0 |

## What moved to appendices (text unchanged, a summary stays in the body)

- Object registry: the example table and the paragraphs on the registry, on
  objects in U memory and on objects in T memory.
- Cost of each policy: the per-policy table with its two paragraphs.
- Registry and memory costs: the two paragraphs.
- Measurement method: switches, order of variants, slicing, result check,
  calibration.
- PoC 2 (nginx/libpcre): the narrative; the outcome table stays in the body.

## What differs from the plan

The plan's estimates for shortening were too high (background, taxonomy and
introduction gave about half of what was estimated), so three things were
added to reach the limit:

- The SP1 coverage table and the SP2/SP3 coverage table are one table with
  the same numbers (the SP1 columns were added to the integrity table).
- PoC 2 is summarized in two sentences in the body.
- The lists of origin classes in Section 6.3 are prose, and several smaller
  sentences that repeated earlier text were removed in Sections 2 to 7.

Shortened text of the original submission is not marked in blue (the `\rev`
markup marks additions); `git diff ba23a2a..41d71b8` shows every change.

## Checks

- Numbers (`token-conservation.json`, the skill's
  `check_revision_token_conservation.py` on the whole paper before and after):
  the only numbers that occur less often are the field totals that were in
  both coverage tables and small integers in removed prose and in the box
  padding; the numbers that occur more often are the ones the body summaries
  repeat from the appendices (8.0, 5.9, 5.5, 2.6, 22, 3.8, the PCRE version).
  The CVE identifiers the checker lists as removed are still in the text,
  without parentheses.
- Citations: 44 distinct keys cited before and after, none lost.
- Labels: none lost; four new appendix labels, all referenced.
- Tables on the page of their text: Tables 2 and 3 on page 10 (their
  paragraphs are on pages 9 and 10), the coverage table on page 11 with both
  coverage paragraphs, the security table on page 12 with Section 7.3.
- The abstract was not changed; no number that it states changed.

## Open, from the call for papers

- AI disclosure: JH on 2026-11-19, "Leave as is for now"; to be decided before
  submission (the call asks for it in the acknowledgments section).
- The call asks that potential harms are discussed in the body; the ethics
  text is Appendix B.
- The margin is about ten lines on page 13.
