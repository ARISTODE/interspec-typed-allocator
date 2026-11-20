# Style Profile

Samples: [E] early InterSpec draft (2026, weight 2), [S] SoK (2024, weight 2), [K] KSplit (2022, weight 1). Quotes are verbatim. Rates are per 100 sentences unless stated. EuroS&P and systems-security conventions come first; this profile is a soft guide to form and never changes a claim, number or hedge.

## 1. Profile in one paragraph

The author writes medium-length declarative sentences (mean about 20 words, few above 35) that each carry one claim, with a concrete subject (the system, a policy, the wrapper, T, U, or "we") and an active present-tense verb. A paragraph opens with a topic sentence, then proceeds in short steps; an enumeration is announced with its count and then given one sentence per item, where the current text packs the items behind a colon or semicolons. Connectives are few and sentence-initial ("However,", "For example,", "While ..."), reasons sit inside the sentence ("because", ", so", "therefore"), and consequences are often attached as a closing ", V-ing" clause. Explanatory colons, dash asides, rhetorical questions and stacked "which" clauses are almost absent.

## 2. Six dimensions

**D1. Sentence length and rhythm.** Mean 19.8 [K] / 20.8 [S] / 19.6 [E] words (current 22.7); median 17 / 19 / 18 (current 21); SD 10.6 [S], 9.5 [E]; sentences of 35+ words 10% / 8% / 6% (current 16%); sentences of 12 words or fewer 35% / 20% / 21%. Rhythm is steady; a short sentence closes a point. Long sentences are lists, not nested clauses.
- "Today, these decisions are largely manual." [E]
- "However, P3 is generally not considered enforced." [S]
- "Simple device drivers finish in under a minute." [K]

**D2. Paragraph length.** 4.4 sentences, 87 words [E]; 5.3 sentences, 110 words [S]; [K] 11.1 is an extraction artifact. Current: 4.4 sentences, 99 words (about 14% heavy in words). In [E], introduction and evaluation paragraphs run 5 to 9 sentences, definition and policy paragraphs 2 to 4. Shape: topic sentence, short steps, an example, then a consequence, limit or pointer.
- Opening: "SP1 restricts which data the untrusted compartment can read." [E]
- Opening: "We measure the overhead InterSpec adds on top of RLBox isolation." [E] (25 of 117 paragraphs in [E] open with "We")
- Closing: "Therefore we leave the study of this interface to future work." [S]

**D3. Vocabulary.** Hedges: "can" (3.8 [E], 8.3 [S] per 1,000 words), "may" (3.4, 1.9), "could" (0.9, 1.3); also "generally", "typically", "often"; "might" at most 0.2. Transitions: sentence-initial "However," (1.7 [E], 5.7 [S]; mid-sentence "however" 0.0 and 0.2), "For example," (2.2 to 2.8 in all three), "While" as opener, "Similarly,", "In contrast,", "Conversely,", "First, Second, Third". "Moreover/Furthermore" at most 0.5; "Specifically" 0 in [E]. Reporting verbs for prior work: classify, refine, term, introduced, identified, categorized, proposed. Own work: present, infer, enforce, evaluate, measure, assume, leave. Formality is moderate, with plain verbs; a defined term is repeated exactly, never varied.
- "This can reduce oversharing because unnecessary data may never be copied into the untrusted domain." [E]
- "However, SafeDrive does not enforce the remaining security properties." [S]
- "Narayan et al. categorized interface attacks into insecure data flow and insecure control flow." [E]

**D4. Citation integration.** Measured on the [E] LaTeX: 83 citation commands in 120 paragraphs (introduction 1.9 per paragraph, background 1.5, evaluation 0.2). 31 of 83 (37%) follow a system name or "X et al." that is the grammatical subject; the rest close a clause, 40% of all as multi-key groups. Related systems are subjects with present-tense verbs.
- "Lefeuvre et al. term these Compartment Interface Vulnerabilities (CIVs)." [E]
- "LXFI enforces API integrity through capabilities and annotations but relies on manually specified rules." [E]

**D5. Modifier style.** Lean and concrete. Adjectives classify ("field-level", "copy-based", "untrusted"); evaluative intensifiers (significant, substantial, highly, crucial) appear in 0.2 of [E] sentences. Claims are tied to named fields, functions and counts. Inline examples use "such as" (6.7 [E], 4.7 [S]) and seldom "e.g." (0.6 [E]).
- "For example, the ssl_ctx_st structure in Figure X contains over 100 fields, including sensitive data such as private key references (cert)." [E]
- "MEM3 (type selector) is rare, with only 3 instances in the power_meter driver." [S]

**D6. Register shifts.** Small. Introduction: gap narrative with "However," and "Yet,", then "We + verb" contributions. Background and taxonomy: definitions ("X occurs when", "X refers to"). Design: procedural, with "the wrapper" or "the analysis" as subject and "If"/"When" conditionals. Evaluation: number first, cause next. Limitations: plain negatives ending in future work.
- "Data leakage CIVs occur when the untrusted compartment can read sensitive information from trusted code through interface data." [E]
- "If either condition is absent, no information flows through X." [E]
- "We leave insecure control flow and temporal CIVs for future work." [E]

## 3. Editing rules

**Do**
1. Open a paragraph with a topic sentence naming its subject or action. "We evaluate InterSpec on 10 library isolation boundaries across 8 applications." [E]
2. Announce an enumeration with its count, then give one sentence per item, with "First, Second, Third" for reasons. "Insecure data-flow CIVs take two forms." [E]
3. Use a concrete subject and an active present verb. "KSplit adds 30 cycles for marshaling simple scalar fields, such as integers." [K]
4. Introduce an example with "For example," (or mid-sentence ", for example,") and name the field or function. "For example, a malicious driver supplying a zero divisor can trigger a divide-by-zero exception and subsequent kernel panic." [S]
5. State a contrast or limit with sentence-initial "However," or "While X, Y", or as "X, not Y". "InterSpec enforces pointee domain integrity, not object bounds validation." [E]
6. Keep a short reason in the same sentence with "because", ", so" or "therefore". "The expected domain is U, so SP3 validates that the pointer remains inside sandbox memory." [E]
7. Attach one consequence as a closing ", V-ing" clause (approx. 9.7 [E], 15.5 [S]; current 5.1). "Fields protected by SP1 are excluded from copy-in, preventing information leakage to U." [E]
8. Link back with "This + noun". "This reasoning leads to the inference rule below." [E]
9. Report a result as scope, subject, count of total, percent; give the cause in the next clause or sentence. "Across the 10 boundaries, SP1 protects 3,179 of 7,523 interface fields (42.3%)." [E]
10. Close a limitation with a deferral or section pointer. "We leave validation for other field types to future work." [E]

**Do not**
1. No colon followed by an explanation (colons 1.7 in [E], 8.5 now); write two sentences. A colon may introduce only a short numbered list. "Control flow transfer CIVs fall into two categories: (1) interface bypass and (2) interface temporal violations." [S]
2. No semicolon chains. At most one semicolon, joining two short parallel clauses; otherwise split. "These designs prevent U from directly dereferencing T memory; pointer values copied back to T still require validation before T dereferences them." [E]
3. No more than one ", which" or ", where" clause per sentence (", which" 5.0 [E], 3.4 [S]; current 9.3). "Origin analysis traces its value to a buffer allocated within U's code, so the pointer is expected to reference U memory." [E]
4. No sentence above about 35 words unless it is a list; split at "and", the colon or the semicolon. "SP3 rejects the corrupted pointer before T reads through it." [E]
5. No dash asides (none in [S] and [E] prose); use parentheses. "MEM5 (corrupted string) is less common, with only 26 instances in total." [S]
6. No rhetorical questions (0 in [E]; [S] has only numbered research questions); state the problem. "The challenge is therefore not only how to compartmentalize an application, but how to protect compartment interfaces." [E]
7. No mid-sentence "however" and no "Moreover", "Furthermore" or "Specifically". "However, these mechanisms are motivated by compatibility, synchronization, and performance." [E]
8. No evaluative intensifiers; give the number. "Their measured deltas are near zero and often negative since omitted fields reduce copy volume." [E]

## 4. Conflicts with venue conventions (do not copy)

- **Errors in the samples.** "often lack an incomplete understanding" [S]; "there are plenty of CIVs can be exploited" [S]; the fragment "Finally, as a quick comparison with previous systems that synchronize only shared fields mainly for performance." [E]; "; so" after a semicolon [E].
- **Informal usage.** Contractions ("doesn’t limit" [S]), "pretty rare" [S], sentence-initial "But overall" [S] and "Plus a range of" [K].
- **Unsupported strength.** [S] uses "highly effective", "significantly", "We believe" (4 times) and double hedges ("could potentially"); [E] has "a much higher coverage". Reviewers read these as overclaiming; keep every hedge and scope of the current text.
- **Numerals.** "2 boundaries (nginx/libpcre, memcached/bipbuffer) are tested" [E] starts a sentence with a digit; "2791 out of 7523" [E] lacks separators.
- **Tense.** Prior work is mixed ("classify", "categorized"); choose one per section.
- **Choppiness.** Do-2 can yield "SP3 targets pointer values that T receives from U. SP3 validates these pointer values before T dereferences them." [E]; merge adjacent sentences that repeat the subject.
- **Passive.** Samples 17 to 19%, current 12%. Do not add passives to match; the venue prefers a visible agent.
- **[K] habits.** Dash asides (10.5) and "e.g.," (9.0) belong to the older paper.

## 5. Before and after (from current.txt)

**1. Introduction (55 words)**
Before: "Prior work classifies CIVs into three categories: insecure control-flow CIVs, which hijack execution in a trusted compartment through corrupted function pointers, unexpected callback invocations, or illegal call sequences; temporal CIVs, which exploit concurrency and ordering assumptions such as time-of-check-to-time-of-use (TOCTTOU) races; and insecure data-flow CIVs, which leak or corrupt interface data exchanged across the boundary."
After: "Prior work classifies CIVs into three categories. Insecure control-flow CIVs hijack execution in a trusted compartment through corrupted function pointers, unexpected callback invocations, or illegal call sequences. Temporal CIVs exploit concurrency and ordering assumptions such as time-of-check-to-time-of-use (TOCTTOU) races. Insecure data-flow CIVs leak or corrupt interface data exchanged across the boundary."

**2. Design (46 words)**
Before: "If either condition is absent, the pointer does not require SP3 validation: a pointer value that U cannot define or modify is protected by SP2 and not copied back to T, and T does not access the memory referenced by a pointer that it never dereferences."
After: "If either condition is absent, the pointer does not require SP3 validation. If U cannot define or modify the pointer value, the value is protected by SP2 and not copied back to T. If T never dereferences the pointer, T does not access the memory that it references."

**3. Evaluation (47 words)**
Before: "Measured in isolation, a registry check of a pointer takes 2.6 ns without the lock, as in all library workloads, which use a sandbox from one thread, and 22 ns with the reader-writer lock, as in our two servers; nearly all of the difference is the lock."
After: "Measured in isolation, a registry check of a pointer takes 2.6 ns without the lock and 22 ns with the reader-writer lock. All library workloads use a sandbox from one thread and run without the lock; our two servers run with it. Nearly all of the difference is the lock."
