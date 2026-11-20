# Style calibration and section reviews of the paper (W4 follow-up)

2026-11-19 (PT). JH: "Please run another run of reviews with subagents, ensure
the writing quality. And to do style calibration, let's try to use ksplit, and
https://arxiv.org/pdf/2412.16754, all are my works before. And I like early
writing in the current paper as well." Done with the style-calibration
protocol of the `academic-paper` skill. Paper branch
`claude/nifty-cray-ik99hh`, commits `1994d01..f81181e`; `main` is unchanged
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
| Words per sentence, mean | 19.6 | 20.8 | 19.8 | 22.7 | 18.6 |
| Words per sentence, median | 18 | 19 | 17 | 21 | 18 |
| Sentences of 35 words or more | 6% | 8% | 10% | 16% | 3% |
| Semicolons per 100 sentences | 5.0 | 3.4 | 5.6 | 9.0 | 2.6 |
| Colons per 100 sentences | 1.7 | (lists) | (lists) | 8.5 | 0.7 |
| Words per paragraph | 87 | 110 | n/a | 99 | 93 |

## Reviews

Three reviewers, one per group of sections (1 to 4; 5 and 6; 7 and 8), each
with the profile, the writing-quality checklist of the skill and the April
text. They could split and rephrase sentences but not change content,
numbers, hedges, citations or length. About 100 sentences were changed.
Follow-ups from their reports: `Nginx` capitalized in prose and `runtime` as
in the April text, SFI defined, one wording for the confused-deputy sentence,
the baseline of the per-policy costs named, the memory number stated for both
servers. Two statements that the paper made twice are made once (Sections 6.2 and
6.3); this pays for the splits. Seven long paragraphs got a paragraph break.

## Checks at `f81181e`

- `token-conservation.json`: the numbers of the paper are the same multiset
  before and after. 141 citation uses before and after, no key lost, no label
  lost.
- Build (`build.log.gz`, `section-lengths.txt`): 21 pages, no errors, no
  overfull boxes; the body ends on page 13; tables on the pages of their text.
- Independent check of meaning and readability on the whole diff
  (`1994d01..5ef8b80`): no changed number, no wrong "respectively", no moved
  citation. Its findings, all fixed in `f81181e`: one antecedent broken by a
  split (PoC 1, "this update"), one sentence separated from the counts it
  qualifies by a new paragraph break, one quantifier made explicit ("every
  pointer"), four over-split passages (a run of four "It" sentences, two
  fragments, the list of the four complete programs), two paragraph breaks at
  the wrong place, and the shortened description of the kernel frameworks in
  Section 2.2, which had dropped facts stated nowhere else and is restored.
  It judged the text slightly shorter-sentenced than the samples and close to
  them otherwise.

## Left for JH (content, not style)

1. The introduction says prior work classifies CIVs into three categories;
   Section 2.1 says two (data flow and control flow).
2. The threat model lists unintended cross-boundary calls, callbacks and call
   sequences among the attacker's goals; Section 5.1 puts control-flow and
   temporal CIVs out of scope.
3. Section 7.2 says 55 pointer fields require SP3; the developer-effort
   paragraph says the wrappers check 20 pointer fields. The text does not
   relate the two counts.
4. The coverage table has nginx/libpcre with 0 fields that need SP3 and 100%;
   PoC 2 and the limitations discuss the name table of `pcre_fullinfo`, which
   the analysis does not report.
5. The wrapper appendix was described in Section 6.2 as combining selective
   copying with "the domain checks of SP3"; it now says "the checks of SP3",
   which is what the appendix shows.
6. Section 7.1 gives the geometric mean of the complete programs (0.8%) but
   not that of the library workloads (0.2%, in the table only).
