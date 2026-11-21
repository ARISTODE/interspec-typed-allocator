# New introduction and citation check of Sections 1 to 3

2026-11-21 (PT). Paper commits `8a3d0f4..c1c2b46`, on `main` since 13:13 PT.
Done with the `academic-paper` skill: the introduction guide, the style
profile, and the citation-check mode (`citation_compliance_agent`; IEEE style,
so the mode reports and the author decides on corrections, which JH asked for:
"use academic skill to ensure our citations are correct").

## Introduction (`584133d`)

JH's outline: compartmentalization helps; isolated software can still be
attacked through interface data, shown with examples from prior work,
including a data-only attack; prior work studied this attack surface but
automated protection is lacking; our goal is to close it automatically; one
highlighted sentence, the problem. The evidence comes from the cited papers
read in full (`FACTS-intro-sources.md`, verbatim quotes with pages). Of five
top-tier introductions in the area that were checked, only the NDSS'23 CIV
paper highlights text (its research questions, in italics).

## Citation check (`ad79eeb`, `c1c2b46`)

- `METADATA.md`: the 29 references cited in Sections 1 to 3 against Crossref
  and the venue pages (DBLP answered with a bot challenge). 26 correct, 3
  wrong: `hacks` (authors, title, venue, DOI), `dui` (book chapter type, so the
  venue was not printed), the driver SoK (no journal; JH chose the published
  ACSAC 2025 version, "Beyond Driver Isolation -- Triaging Threats against
  Driver Isolation"). Also fixed: page ranges with a Unicode dash, braces for
  acronyms in titles, two titles with stray spaces, eight missing DOIs, the
  `schluter2025prefence` entry (published at EuroS&P 2025; outside Sections 1
  to 3, found by the bibtex warning) and a duplicate `lxfi` key replaced by
  `Mao11LXFI` in Section 5. bibtex now reports no warning (`bibtex.out`).
- `CLAIMS.md`: every citing sentence of Sections 1 to 3 against the text of
  its source. 13 sentences said more than the source and are reworded; none
  was unsupported as a whole. Among them: "found such flaws" instead of
  "shown such attacks"; the Firefox case as a conditional on the renderer;
  "program analysis" instead of "static analysis" (DUI uses dynamic taint);
  data-flow CIVs "account for most of the CIVs that these studies report"
  instead of "the most prevalent class"; RLBox locates validation sites
  automatically and was deployed for a font shaping library; the DUI name;
  the ConfFuzz taxonomy is not presented as a refinement. On JH's decision the
  introduction no longer gives a per-driver CIV count from the driver SoK.
- Not verified at full text: Butt et al. (ACSAC 2009) and the ACSAC 2025
  version of the driver SoK, whose hosts are blocked from this session; the
  sentences citing Butt et al. were worded to what its abstract supports.

Build (`build.log.gz`): 21 pages, no errors, no overfull boxes; the body ends
on page 13 (`section-lengths.txt`).
