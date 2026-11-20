# Introduction rewritten around the problem and the running example

2026-11-20 (PT). Paper commits `f81181e..8a3d0f4`, merged to `main` on JH's
instruction ("please update the repo directly now, merge to main, and then I
can check"). Done with the `academic-paper` skill (revision rules, the
introduction guide, the style profile of `../04-style-and-review/`, the token
and acronym checks).

JH's requirements, from four rounds of drafts shown in the session: the
problem must arrive early and be intuitive; less background and no CIV
classification in the introduction; only necessary terms; no T/U; state that
this is the security gap of isolation that the paper addresses; bold only on
the problem and the gap; one attack, with a note that other kinds exist; a
running example, bringing the later example forward.

What changed:

- Paragraph 2 states the problem in bold (isolation does not protect the
  interface) and defines compartment interface and interface data.
- The Nginx/OpenSSL running example and Figure 1 move from Section 5.1 to the
  introduction. One attack is shown (the overwritten `verify_cb` callback).
- The gap is stated in bold, with the scope (insecure data-flow CIVs; CIVs of
  call order or timing are outside the scope).
- The three decisions, one sentence each; a paragraph on what existing
  systems leave open; the observation behind the inference; InterSpec and its
  three policies without T/U; enforcement, tied back to the example.
- The contribution list and the results paragraph are unchanged.
- To stay on 13 pages, sentences that only repeated the new introduction were
  removed from Sections 2.1, 5.1 and 5.3 (the confused-deputy sentence, the
  repeated definition of interface data, the "two main cases" sentence, the
  second description of the `verify_cb` attack). Section 5.1 is titled "Scope
  and Running Example".

Checks at `8a3d0f4`: an independent proofread compared every statement of the
introduction with the rest of the paper; its findings are fixed (the three
observations follow the inference rules exactly, "can largely be automated",
the goal sentence, the scope sentence, one missing step in the example).
`token-conservation.json`: the only new numbers are 214 and 350,000 (Section
7.2: 214 functions, 351,808 interface fields); no citation key lost, no label
lost. Build (`build.log.gz`): 21 pages, no errors, no overfull boxes; the body
ends on page 13 (`section-lengths.txt`). The introduction has 17 words per
sentence on average, no colon-led explanation and no semicolon.

Noted by the proofread, not changed (content): Section 6.3 and Section 7.2
say that Nginx handles OpenSSL's `SSL_CTX` only through OpenSSL's API, while
the running example has Nginx read and invoke a field of a simplified
`ssl_ctx`; "PoC" is used in Section 7.3 without being spelled out.
