# Style calibration and section reviews of the paper (W4 follow-up)

2026-11-19 (PT). JH: "Please run another run of reviews with subagents, ensure
the writing quality. And to do style calibration, let's try to use ksplit, and
https://arxiv.org/pdf/2412.16754, all are my works before. And I like early
writing in the current paper as well." Done with the style-calibration
protocol of the `academic-paper` skill. Paper branch
`claude/nifty-cray-ik99hh`, commits `1994d01..5ef8b80`; `main` is unchanged
at `dcb2c60`.

## Samples and profile

- Samples (`samples.sha256` for the two PDFs): the KSplit paper (OSDI 2022),
  the SoK on the attack surface of driver isolation (arXiv 2412.16754, 2024),
  and the April version of this paper (`c692d95`). The recent two are
  weighted more, as the protocol says.
- `STYLE_PROFILE.md`: the profile, with quoted examples, a Do and a Do-not
  list, and what not to copy from the samples.
- `style-stats-before.json`, `style-stats-after.json`: measured with
  `tools/paper_style_stats.py` on text extracted with `tools/paper_detex.py`.

| | April version | SoK | KSplit | Paper before | Paper after |
|---|---:|---:|---:|---:|---:|
| Words per sentence, mean | 19.6 | 20.8 | 19.8 | 22.7 | 18.4 |
| Words per sentence, median | 18 | 19 | 17 | 21 | 18 |
| Sentences of 35 words or more | 6% | 8% | 10% | 16% | 3% |
| Semicolons per 100 sentences | 5.0 | 3.4 | 5.6 | 9.0 | 2.6 |
| Colons per 100 sentences | 1.7 | (lists) | (lists) | 8.5 | 0.7 |
| Words per paragraph | 87 | 110 | n/a | 99 | 91 |

## Reviews

Three reviewers, one per group of sections (1 to 4; 5 and 6; 7 and 8), each
with the profile, the writing-quality checklist of the skill and the April
text. They could split and rephrase sentences but not change content,
numbers, hedges, citations or length. About 100 sentences were changed.
Follow-ups from their reports: `Nginx` capitalized in prose and `runtime` as
in the April text, SFI defined, one wording for the confused-deputy sentence,
the baseline of the per-policy costs named, the memory number stated for both
servers. Three statements that the paper made twice are made once (Sections
2.3, 6.2, 6.3); this pays for the splits. Nine long paragraphs got a paragraph
break.

## Checks at `5ef8b80`

- `token-conservation.json`: no number removed; 6.7 and 8.6 occur once more
  (the introduction now names each value in its own sentence). 141 citation
  uses before and after, no key lost, no label lost.
- Build (`build.log.gz`, `section-lengths.txt`): 21 pages, no errors, no
  overfull boxes; the body ends on page 13; tables on the pages of their text.
- An independent check of meaning and readability on the whole diff is
  recorded in the tracker Log when it is back.

## Left for JH (content, not style)

See the tracker Log line of this pass.
