# The two open co-author comments in `eval.tex` (W4): parsing and checks

2026-11-19 (PT), paper `main` at `dcb2c60`. Made with the `revision-coach`
mode of the `academic-paper` skill (academic-research-skills `414fab4`,
installed for the session user on JH's request of the same day). This is the
skill's parsing preview: the paper is LaTeX, so no block manifest or
`revision-roadmap/1.1` file was produced, and no choice below is made for JH.

## Items, in source order

| Ref | Source | Location | What it asks | Kind | Obligation | Where a change would go |
|---|---|---|---|---|---|---|
| TJ-1 | `\trent` | `tex/eval.tex:288`, after "Cost of the registry operations" | memcached/bipbuffer has two pointers to validate. What would the overhead be if their updates were protected inside the domain and proved memory safe? Checking at the boundary is not the only defense, and this could be a finding. | question plus suggested analysis | consider (co-author suggestion, no requirement stated) | a sentence in that paragraph or in Limitations ("Object metadata"), or a new experiment |
| HA-1 | `\hamed` | `tex/eval.tex:435`, after Table `tab:integrity_coverage` | The table font may be too small; try `\footnotesize` if it fits. | editorial | consider | line 402 of `tex/eval.tex` |

Both comments are hidden in the PDF (`\showcommentsfalse`).

## Checks

- HA-1: the table already uses `\footnotesize` (`tex/eval.tex:402`), as do
  the other five tables of the section. One size larger (`\small`,
  `variant-small.diff`) also fits: the build has the same 22 pages and the same
  two overfull boxes as `main` (`build-base.log.gz`, `build-small.log.gz`), and
  the table stays on page 16.
- TJ-1: existing measurements that bear on the question: SP3 alone at
  memcached/bipbuffer costs 0.8% (range -2.3 to +5.4, includes zero) and one
  check in the locked registry takes 22 ns
  (`../../R1/06-repetition-quiet-2d2c3af/README.md`). A defense inside the
  domain could save at most this. No in-domain protection was built or
  measured.

## Found on the way: venue format

The paper uses the ACM `acmart` class on US Letter; its body ends on page 17.
The EuroS&P 2027 call (D3) asks for the IEEE conference template on A4 and at
most 13 pages of body text, with references and appendices outside the limit
(call for papers as reported by a web search on 2026-11-19; the conference
host is not reachable from this session). A trial conversion
(`variant-ieee.diff`: class, title block, bibliography style; nothing else)
builds without errors (`build-ieee.log.gz`): 23 pages on A4, the body ends
about six tenths down page 18, and one table is 14 pt too wide. The body is
about 4.6 pages over the limit. Nothing was changed in the paper repository.
