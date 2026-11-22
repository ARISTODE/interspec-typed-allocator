# How strong systems-security papers write introductions, and what that means for InterSpec's

Analysis done on 2026-11-22 with the academic-paper skill's introduction guide
(CARS model: Move 1 territory, Move 2 niche, Move 3 occupy) and its writing-quality
checklist. Introductions were extracted with pdftotext; the extracted texts are in
`work/clean/` (A–H). Every quote was checked by script against these texts.
Word counts exclude citations. PF = point-first (a claim in plain words, citations
support it); NE = a named example serving a stated point; SF = system-first (the
sentence is about a named system and describes it).

Papers: A RLBox (USENIX Security 2020); B ERIM (USENIX Security 2019); C Lefeuvre
et al., CIVs (NDSS 2023); D Data-Oriented Programming (IEEE S&P 2016); E Glamdring
(USENIX ATC 2017); F KSplit (OSDI 2022, the author's); G SoK on driver isolation
(arXiv 2412.16754, the author's); H the current InterSpec introduction (paper
`c1c2b46`).

## 1. At a glance

| | Words | M1/M2/M3 % | Problem first stated | PF/NE/SF (+own) | Emphasis, RQs, insight, list, results |
|---|---|---|---|---|---|
| A RLBox | 1,287 | 5/44/51 | ¶2, word 62 (5%) | 6/3/1 (+6) | italic terms; run-in "Contributions."; numbers |
| B ERIM | 974 | 8/33/59 | ¶2, word 147 (15%) | 4/5/0 (+2) | italic contrast; a question; numbered contributions; numbers |
| C Lefeuvre | 864 | 19/32/49 | ¶3, word 161 (19%) | 10/0/0 | italic RQs; bullets; results as three insights |
| D DOP | 944 | 10/19/71 | ¶2, word 97 (10%) | 5/1/0 | "The key idea…"; bold run-in heads; bullets; numbers |
| E Glamdring | 941 | 15/18/67 | ¶1, word 21 (2%); gap ¶3, word 174 (18%) | 9/1/1 (+4) | bold RQ; "We exploit the observation…"; numbers |
| F KSplit | 1,210 | 16/27/57 | ¶3, word 190 (16%) | 6/2/1 (+1) | no emphasis, RQ, insight or list; numbers |
| G SoK | 867 | 22/37/41 | ¶3, word 189 (22%) | 9/2/1 (+1) | bold statistic, Table 1; four RQs; bullets |
| H current | 1,145 | 12/34/54 | ¶2, word 136 (12%); own gap ¶4, word 400 (35%); precise problem ¶5, word 604 (53%) | 8/4/5 (+2) | 11 italic terms, one bold sentence; no RQ or insight; four bullets; eight figures |

## 2. Paper notes

**A. RLBox.** ¶1 M1 "All major browsers today employ coarse grain privilege separation…"; ¶2 M2 "Unfortunately, this is no longer enough: nearly everything we care about today is done through a website."; ¶3 evidence; ¶4 scenario "To appreciate the impact of these vulnerabilities…"; ¶5–6 why Site Isolation falls short; ¶7 M3 "To mitigate these vulnerabilities, we need to harden the renderer itself."; ¶8 "Making this practical poses three significant challenges…"; ¶9–11 design; ¶12–16 results, contributions. Citations: PF "By compromising the renderer, an attacker gets total control of the current site and, often, any other sites the browser has credentials for [14]."; NE "For example, an out-of-bounds write in libvorbis was used to exploit Firefox at Pwn2Own 2018 [7]."; its one SF explains itself ("…support Site Isolation [41], which isolates different sites from each other…"). Research systems are one category deferred to §8. Intuition: the Alice/Trudy scenario; "over 93% of the sites load at least one such cross-origin resource".

**B. ERIM.** ¶1 M1; ¶2 SFI's cost; ¶3 page tables' switch cost; ¶4–6 M3 "In this paper, we present ERIM, the first isolation technique for x86…"; ¶7–8 results and contributions. Citations: NE "Recent work such as Wedge, Shreds, SeCage, SMVs, and light-weight contexts (lwCs) [10, 13, 24, 33, 34] have reduced the overhead of such switching, but the cost is still substantial." (the main clause carries the point; the reader needs to know none of the names); PF "Techniques based on Intel VT-x extended page tables with VMFUNC [34] have less overhead, but the overhead is still high…". Intuition: one number per rival approach.

**C. Lefeuvre et al.** ¶1–2 M1 "The principle of least privilege has guided the design of safe computer systems…"; ¶3 M2 "Unfortunately, breaking down applications into compartments means that control and data dependencies through shared interfaces create new classes of vulnerabilities [61]…"; ¶4 gap; ¶5 italic RQs; ¶6–8 M3. Citations all PF, e.g. "almost all modern compartmentalization frameworks [67], [60], … [1] neglect the problem of securing interfaces" (13 frameworks, none named); prior work appears as attack classes ("objects passed through APIs can be corrupted to launch confused deputy attacks [39], [21]"). Intuition: italic RQs, the OpenSSL key extraction, Listing 1 next to the introduction.

**D. DOP.** ¶1 M1 "Control-hijacking attacks are the predominant category of memory exploits today."; ¶2 "A natural question is to analyze the limits of protection offered by control-flow defenses…", ending on the belief it overturns; ¶3 M3 "In this paper, we show that non-control data attacks with rich expressiveness can be crafted…". Citations: PF, and NE that pair each acronym with what it does ("protection of code pointers (CCFI, CPI) [12], [13]"). Intuition: control plane vs data plane; "The key idea in our construction is to find data-oriented gadgets…".

**E. Glamdring.** ¶1–2 M1; ¶3 "Haven [6], Graphene [55, 81] and SCONE [2] have demonstrated the feasibility…", immediately followed by "By placing all code inside the enclave, these approaches, however, have a large trusted computing base (TCB)…"; ¶4 partial mitigations; ¶5 "We want to explore a different design point…" (bold question); ¶6–8 approach and results. Citations: PF "proposals for securing applications with enclaves [68, 72, 73] introduce additional checks in enclave code…" (systems unnamed). Intuition: "what is the minimum functionality of an application that must be placed inside an enclave…"; "We exploit the observation that…".

**F. KSplit (author).** ¶1–2 M1 "Device drivers have long been and continue to be a major source of defects…"; ¶3 M2 "Despite the availability of low-overhead isolation mechanisms, the task of isolating existing driver code remains challenging."; ¶4 manual analysis; ¶5 M3 "In this paper, we present KSplit…"; ¶6–9 challenge → technique; ¶10 results. Citations: NE with gloss ("For example, LXFI, an SFI framework, utilized an iterative procedure…"); one SF ("Decaf [72] and Microdrivers [33] took initial steps towards automated analysis…") after the same works were cited bare. Intuition: scale ("require analysis of 459 functions and around 10,000 object fields").

**G. SoK (author).** ¶1–2 M1 "Today's Linux 6.5 kernel contains roughly 9,921 device drivers…"; ¶3–6 four gaps, "Despite recent advances, the security benefits of driver isolation remain unclear."; ¶7–9 RQs, contributions, scope. Citations: PF ("scalable automated decomposition approaches, such as static analyses for automating kernel-driver code and data separation [19], [30]" cites Microdrivers and KSplit by what they do), PF "as demonstrated by Lefeuvre et al. [36]", one SF ("Chien et al. [13] identify…"). Intuition: Table 1 and the bold "16–59%".

**H. Current.** ¶1 M1; ¶2 "However, isolation alone does not make a compartmentalized application secure."; ¶3 "Lefeuvre et al. [assess_civ] term such flaws…"; ¶4 prior work and the bold gap; ¶5 aim, scope, three decisions; ¶6–7 InterSpec, wrappers, contributions; ¶8 results. 19 citing sentences, 5 SF (more than A–E together). Good NE: the Firefox sentence. No field or pointer to picture, no question, no insight sentence.

## S1. What A–E share

1. Order: territory ≤ 20%; a pivot ("Unfortunately", "However", "A natural question") states the problem by 2–19%; the stakes; why existing approaches fail, one category at a time, each with a number or concrete limit; then the key idea and the system, whose purpose sentence answers the shortfalls.
2. Citations make points: 34 PF, 10 NE, 2 SF across A–E, and both SF sentences explain the system in the same sentence. Prior systems are grouped by what they do; names appear only as examples after the claim.
3. Something to picture: a scenario, a listing, a two-plane model, a question.
4. An explicit idea ("The key idea…", "We exploit the observation that…").
5. Sparse emphasis.

## S2. The author's own patterns (F, G)

Keep: numbers that make the effort tangible ("over 900,000 object fields—a number that is well beyond the reach of manual analysis"); challenge → technique pairs; G's numbered RQs, Table 1 and point-first citations. Avoid: long mixed paragraphs that cite the same works twice (F ¶4, 228 words); no insight sentence (F); repeated "crucial"/"important" (G); vague PF ("Other researchers have identified additional security issues…"); author-first sentences ("Lefeuvre et al. …"), which H carries over three times.

## S3. Diagnosis of H

System-first sentences, or sentences that assume the reader knows a cited work:
1. "Lefeuvre et al. [assess_civ] term such flaws Compartment Interface Vulnerabilities (CIVs)." (author-first)
2. "Lefeuvre et al. found 629 potential CIVs in 39 compartmentalization scenarios across 25 applications…" (author-first)
3. "Lefeuvre et al. observe that almost all compartmentalization frameworks neglect … and that even RLBox relies extensively on manual checking." (RLBox not yet introduced)
4. "The RLBox authors report that writing these checks was the hardest part of retrofitting Firefox." ("these checks" undefined)
5. "Microdrivers and KSplit selectively synchronize shared state, which can reduce oversharing." ("synchronize", "oversharing" undefined)
6. "However, they are primarily designed for compatibility and performance and do not infer security policies for CIV protection at field granularity." (terms defined only later)
7. "…and LXFI relies on manually specified rules." (LXFI unexplained)
8. ¶1's list of mechanisms with 13 citations that the argument never uses.
9. "…integrated with the RLBox framework." (RLBox first called a framework at 72%)

Logic: ¶2 shows that attacks exist, not what crosses the interface; ¶3 and ¶4 both open with prior work and read as a survey; the gap is at 35% and the precise problem (the three decisions) at 53%; ¶5 states the aim before the problem it answers; the terms cycle (three decisions → policies → SP1–SP3); no insight sentence; ¶8 leaks evaluation details.

## S4. Recommended outline

1. M1 (~90 words): least privilege; retrofitted into browser libraries and kernel drivers; contained real flaws (OpenSSH, slaacd). Cut the mechanism list to one clause.
2. M2, the problem: "However, isolation alone does not make a compartmentalized application secure."; define the interface; attacks abuse its data; Firefox, ImageMagick/OpenSSL and DUI as named examples.
3. M2, name and prevalence, point-first: CIVs [assess_civ], confused deputy; the 629 count and the driver study.
4. M2, the precise problem, moved up: data leakage and data corruption, scope, the three decisions in the words SP1–SP3 reuse.
5. M2, the gap judged against the three decisions, point-first; names only as examples; end with the bold sentence.
6. M3, purpose and insight: InterSpec makes the three decisions automatically; how each side accesses each field determines what to copy in, what to copy back, and which pointers to check; SP1–SP3 one per decision.
7. M3, enforcement: wrappers integrated with RLBox and the object registry.
8. Contributions (terms fixed in ¶4). 9. Results (keep the headline numbers; move details to Section 7).
