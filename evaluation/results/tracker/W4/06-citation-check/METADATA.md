# Bibliographic metadata check: 29 cited entries

Input: `citecheck/cited-entries.md` (the first definition bibtex picks, per key).
Checked on 2026-11-21. Result: **26 OK, 3 ERROR, 0 UNVERIFIED**.

## Sources and limits

- **Crossref REST API.** I looked up every entry that has a DOI by its DOI, and the rest by `query.bibliographic`. The 23 responses saved by the earlier run were reused; new responses are in `raw/crossref-*.json`.
- **DBLP could not be used.** Every query to `dblp.org/search/publ/api` returned an HTTP 202 bot-challenge HTML page ("Making sure you're not a bot!") instead of JSON. A retry several minutes later got the same page (sample: `raw/dblp-botchallenge-sample.html`). The mirrors `dblp.uni-trier.de` and `dblp.dagstuhl.de` were refused by the egress proxy (403).
- **Venue pages used instead of DBLP.** For USENIX papers I used the `www.usenix.org` presentation pages, which carry BibTeX, and the legacy abstract pages ("Pp. x–y of the Proceedings"). For NDSS papers I used `www.ndss-symposium.org` paper pages and the published PDFs. arXiv abstract pages were used for the two arXiv entries.
- **Other hosts refused** by the proxy (403): acsac.org, link.springer.com, doi.org, api.openalex.org, api.semanticscholar.org.
- **Rendering test.** I rendered all 29 entries with the repository's own `IEEEtranS.bst` (v1.12) and the paper's `\bibliography{...}` file order. The output is in `render/test.bbl`; no repository file was touched. bibtex reported one warning: `empty journal in huang_sok_attack_surface_device_drv_iso`.

## Results

| key | status | what differs | authoritative value | source URL |
|---|---|---|---|---|
| protection-info-system | OK | — | J.H. Saltzer, M.D. Schroeder, "The protection of information in computer systems", Proc. IEEE 63(9):1278–1308, 1975, doi 10.1109/PROC.1975.9939 | https://api.crossref.org/works/10.1109/PROC.1975.9939 |
| sok-compartmentalization | OK | — (cosmetic: stray spaces inside `{{ SoK: ... }}`, see notes) | Lefeuvre, Dautenhahn, Chisnall, Olivier, "SoK: Software Compartmentalization", 2025 IEEE S&P, pp. 3107–3126, doi 10.1109/SP61157.2025.00075 | https://api.crossref.org/works/10.1109/SP61157.2025.00075 |
| provos2003preventing | OK | — | Provos, Friedl, Honeyman, "Preventing Privilege Escalation", 12th USENIX Security Symposium (USENIX Security 03), 2003, pp. 231–242 | https://www.usenix.org/conference/12th-usenix-security-symposium/preventing-privilege-escalation ; pages: https://www.usenix.org/legacy/events/sec03/tech/provos_et_al.html |
| rlbox | OK | — (booktitle uses the ACM-DL wording of the same proceedings) | Narayan, Disselkoen, Garfinkel, Froyd, Rahm, Lerner, Shacham, Stefan, "Retrofitting Fine Grain Isolation in the Firefox Renderer", 29th USENIX Security Symposium (USENIX Security 20), 2020, pp. 699–716 | https://www.usenix.org/conference/usenixsecurity20/presentation/narayan |
| isolation-without-taxation | OK | — (DOI not given in entry) | Kolosick, Narayan, Johnson, Watt, LeMay, Garg, Jhala, Stefan, PACMPL 6(POPL):1–30, 2022, doi 10.1145/3498688 | https://api.crossref.org/works/10.1145/3498688 |
| xfi | OK | — | Erlingsson, Abadi, Vrable, Budiu, Necula, "XFI: Software Guards for System Address Spaces", 7th USENIX OSDI (OSDI 06), 2006, pp. 75–88 | https://www.usenix.org/conference/osdi-06/xfi-software-guards-system-address-spaces ; pages: https://www.usenix.org/legacy/events/osdi06/tech/erlingsson.html |
| bgi | OK | — | Castro, Costa, Martin, Peinado, Akritidis, Donnelly, Barham, Black, SOSP '09, pp. 45–58, doi 10.1145/1629575.1629581 | https://api.crossref.org/works/10.1145/1629575.1629581 |
| erim | OK | — (USENIX lists "Nuno O. Duarte"; the entry omits the middle initial) | Vahldiek-Oberwagner, Elnikety, Duarte, Sammler, Druschel, Garg, 28th USENIX Security Symposium (USENIX Security 19), 2019, pp. 1221–1238 | https://www.usenix.org/conference/usenixsecurity19/presentation/vahldiek-oberwagner |
| hacks | **ERROR** | (1) `volume={22}`: NDSS proceedings have no volume; it prints as "vol. 22". (2) The 3rd author's surname is "Ortega Perez" (PDF byline) or "Ortega" (Crossref); `Perez, Carolina Ortega` prints "C. O. Perez". (3) `pages={1--17}` is not in any authoritative record; NDSS papers are unpaginated (the PDF has 17 pages). (4) The booktitle "…Symposium. NDSS" is garbled. (5) The DOI is missing. The title "HAKC" matches the PDF, but Crossref and the NDSS web page say "HAKCs". | McKee, Giannaris, Ortega Perez, Shrobe, Payer, Okhravi, Burow, "Preventing Kernel Hacks with HAKC", Proceedings 2022 Network and Distributed System Security Symposium, Internet Society, 2022, doi 10.14722/ndss.2022.24026 | https://api.crossref.org/works/10.14722/ndss.2022.24026 ; https://www.ndss-symposium.org/wp-content/uploads/2022-26-paper.pdf ; https://www.ndss-symposium.org/ndss-paper/auto-draft-257/ |
| bulkhead | OK | — (DOI exists but not given) | Guo, Wang, Bai, Zeng, Lu, "BULKHEAD: …with PKS", NDSS 2025, doi 10.14722/ndss.2025.230328 | https://api.crossref.org/works?query.bibliographic=BULKHEAD… (raw/crossref-search-bulkhead.json); https://www.ndss-symposium.org/wp-content/uploads/2025-s328-paper.pdf |
| ksplit | OK | — | Huang, Narayanan, Detweiler, Huang, Tan, Jaeger, Burtsev, "KSplit: Automating Device Driver Isolation", OSDI 22, 2022, pp. 613–631 | https://www.usenix.org/conference/osdi22/presentation/huang-yongzhe |
| lvds | OK | — | Narayanan, Huang, Tan, Jaeger, Burtsev, VEE '20, pp. 157–171, doi 10.1145/3381052.3381328 | https://api.crossref.org/works/10.1145/3381052.3381328 |
| lxds | OK | — (cosmetic: "LXDs :" has a space before the colon) | Narayanan, Balasubramanian, Jacobsen, Spall, Bauer, Quigley, Hussain, Younis, Shen, Bhattacharyya, Burtsev, "LXDs: Towards Isolation of Kernel Subsystems", USENIX ATC 19, 2019, pp. 269–284 | https://www.usenix.org/conference/atc19/presentation/narayanan |
| sud | OK | — | Boyd-Wickizer, Zeldovich, "Tolerating Malicious Device Drivers in Linux", USENIX ATC 10, 2010 (no page numbers on the USENIX record) | https://www.usenix.org/conference/usenix-atc-10/tolerating-malicious-device-drivers-linux |
| nooks | OK | — (Crossref gives only the start page, 102, which matches) | Swift, Martin, Levy, Eggers, "Nooks: an architecture for reliable device drivers", Proc. 10th ACM SIGOPS European Workshop (EW10), 2002, p. 102–, doi 10.1145/1133373.1133393 | https://api.crossref.org/works/10.1145/1133373.1133393 |
| microdrivers | OK | — | Ganapathy, Renzelmann, Balakrishnan, Swift, Jha, ASPLOS XIII, 2008, pp. 168–178, doi 10.1145/1346281.1346303 | https://api.crossref.org/works/10.1145/1346281.1346303 |
| assess_civ | OK | — The entry's "Chien, Yi" matches the paper's byline. Crossref and the NDSS web page both list "Yi Chen", a metadata typo on their side. | Lefeuvre, Bădoiu, Chien, Huici, Dautenhahn, Olivier, NDSS 2023, doi 10.14722/ndss.2023.24117 | https://api.crossref.org/works/10.14722/ndss.2023.24117 ; byline: https://www.ndss-symposium.org/wp-content/uploads/2023/02/ndss2023_f117_paper.pdf |
| dui | **ERROR** | Entry type `@inbook`: IEEEtranS treats `title` as the book title, prints the paper title in italics as if it were a book, and drops the booktitle "Computer Security – ESORICS 2015". Rendered: *Identifying Arbitrary Memory Access …*, ser. LNCS. Cham: Springer, 2015, vol. 9327, p. 312–331. It should be a conference paper (@inproceedings). The metadata itself (authors, title, pages, DOI) is correct. | Hu, Chua, Liang, Saxena, "Identifying Arbitrary Memory Access Vulnerabilities in Privilege-Separated Software", in Computer Security – ESORICS 2015 (Proceedings, Part II), LNCS, Springer, Cham, 2015, pp. 312–331, doi 10.1007/978-3-319-24177-7_16 | https://api.crossref.org/works/10.1007/978-3-319-24177-7_16 ; volume: https://api.crossref.org/works/10.1007/978-3-319-24177-7 |
| hardy1988confuseddeputy | OK | — (DOI exists but not given) | N. Hardy, "The Confused Deputy: (or why capabilities might have been invented)", ACM SIGOPS OSR 22(4):36–38, 1988, doi 10.1145/54289.871709 | https://api.crossref.org/works?query.bibliographic=… (raw/crossref-search-hardy1988confuseddeputy.json) → 10.1145/54289.871709 |
| huang_sok_attack_surface_device_drv_iso | **ERROR** | (1) `@article` without `journal`: bibtex warns "empty journal", and the entry prints as `"Sok: …," no. arXiv:2412.16754, Dec. 2024, arXiv:2412.16754.`, with the ID twice and a bogus "no.". (2) It is very likely published: Crossref has an ACSAC 2025 paper with the identical 7-author list in the identical order, on the same topic, under a new title: "Beyond Driver Isolation - Triaging Threats against Driver Isolation", pp. 245–261. I could not compare abstracts, because acsac.org and IEEE were unreachable, so the authors should confirm. The arXiv metadata (title, authors, Dec 2024) matches the entry. | arXiv: Huang, Huang, Ennis, Narayanan, Burtsev, Jaeger, Tan, "SoK: Understanding the Attack Surface in Device Driver Isolation Frameworks", arXiv:2412.16754 (v1, 21 Dec 2024, no journal-ref). Published (likely): same authors, "Beyond Driver Isolation - Triaging Threats against Driver Isolation", 2025 IEEE Annual Computer Security Applications Conference (ACSAC), IEEE, 2025, pp. 245–261, doi 10.1109/ACSAC67867.2025.00033 | https://arxiv.org/abs/2412.16754 ; https://api.crossref.org/works/10.1109/acsac67867.2025.00033 |
| civscope | OK | — (cosmetic: renders as "Civscope", see notes) | Chien, Bădoiu, Yang, Huo, Kaoudis, Lefeuvre, Olivier, Dautenhahn, KISV '23, pp. 33–40, doi 10.1145/3625275.3625399 | https://api.crossref.org/works/10.1145/3625275.3625399 |
| microdriver+ | OK | — | Butt, Ganapathy, Swift, Chang, 2009 ACSAC, IEEE, pp. 301–310, doi 10.1109/ACSAC.2009.35 | https://api.crossref.org/works/10.1109/ACSAC.2009.35 |
| invariant_infer_empirical_eval | OK | — | Nimmer, Ernst, "Invariant inference for static checking: an empirical evaluation", ACM SIGSOFT SEN 27(6):11–20, 2002, doi 10.1145/605466.605469 | https://api.crossref.org/works/10.1145/605466.605469 |
| Mao11LXFI | OK | — (booktitle abbreviated to "SOSP") | Mao, Chen, Zhou, Wang, Zeldovich, Kaashoek, Proc. 23rd ACM SOSP, 2011, pp. 115–128, doi 10.1145/2043556.2043568 | https://api.crossref.org/works/10.1145/2043556.2043568 |
| Ferrante87PDG | OK | — (`journal = TOPLAS` macro is defined in bib/tan.bib l.44, before use; renders "ACM Transactions on Programming Languages and Systems") | Ferrante, Ottenstein, Warren, ACM TOPLAS 9(3):319–349, 1987, doi 10.1145/24039.24041 | https://api.crossref.org/works/10.1145/24039.24041 |
| LiuTJ17Ptrsplit | OK | — | Liu, Tan, Jaeger, "PtrSplit: Supporting General Pointers in Automatic Program Partitioning", CCS '17, pp. 2359–2371, doi 10.1145/3133956.3134066 | https://api.crossref.org/works/10.1145/3133956.3134066 |
| lim2024_kernel_compart_sok | OK | — Matches arXiv v1. Crossref title+author searches found no published version, and DBLP could not be checked. | Lim, Agrawal, Han, Eyers, O'Keeffe, Pasquier, "Securing Monolithic Kernels using Compartmentalization", arXiv:2404.08716, Apr 2024 (v1 only, no journal-ref) | https://arxiv.org/abs/2404.08716 |
| wilke2020nosecuritywithoutintegrity | OK | — Only the capitalization differs: the authoritative title has "SEVurity" and the entry has "Sevurity" (see notes). | Wilke, Wichelmann, Morbitzer, Eisenbarth, "SEVurity: No Security Without Integrity: Breaking Integrity-Free Memory Encryption with Minimal Assumptions", 2020 IEEE S&P, pp. 1483–1496, doi 10.1109/SP40000.2020.00080 | https://api.crossref.org/works/10.1109/SP40000.2020.00080 |
| daikon | OK | — | Ernst, Perkins, Guo, McCamant, Pacheco, Tschantz, Xiao, Sci. Comput. Program. 69(1–3):35–45, Dec 2007, doi 10.1016/j.scico.2007.01.015 | https://api.crossref.org/works/10.1016/j.scico.2007.01.015 |

## Corrected BibTeX for ERROR entries

Each corrected entry keeps the original key. I checked that all of them render cleanly with the repository's IEEEtranS.bst (`render/fixed/fixed.bbl`).

### hacks

Built from the Crossref DOI record (venue, publisher, DOI) and the published NDSS PDF (byline and title). The PDF prints the title as "…with HAKC", while Crossref and the NDSS web page say "…with HAKCs"; use either. The authoritative records have no volume and no pages, so neither is included.

```bibtex
@inproceedings{hacks,
  author    = {McKee, Derrick and Giannaris, Yianni and Ortega Perez, Carolina and Shrobe, Howard and Payer, Mathias and Okhravi, Hamed and Burow, Nathan},
  title     = {Preventing Kernel Hacks with {HAKC}},
  booktitle = {Proceedings 2022 Network and Distributed System Security Symposium},
  year      = {2022},
  publisher = {Internet Society},
  doi       = {10.14722/ndss.2022.24026}
}
```

Renders as: D. McKee, Y. Giannaris, C. Ortega Perez, H. Shrobe, M. Payer, H. Okhravi, and N. Burow, "Preventing kernel hacks with HAKC," in *Proceedings 2022 Network and Distributed System Security Symposium*. Internet Society, 2022.

### dui

Built from the Crossref chapter record and the Crossref record of the parent book. The book record gives the volume title "Computer Security – ESORICS 2015, Part II", Springer International Publishing, Cham, ISBN 978-3-319-24176-0.

The LNCS series number 9327 does not appear in Crossref. It is carried over from the original entry and is consistent with Part II; it could not be cross-checked because link.springer.com is blocked.

```bibtex
@inproceedings{dui,
  author    = {Hu, Hong and Chua, Zheng Leong and Liang, Zhenkai and Saxena, Prateek},
  title     = {Identifying Arbitrary Memory Access Vulnerabilities in Privilege-Separated Software},
  booktitle = {Computer Security -- {ESORICS} 2015, Part {II}},
  series    = {Lecture Notes in Computer Science},
  volume    = {9327},
  pages     = {312--331},
  year      = {2015},
  publisher = {Springer International Publishing},
  address   = {Cham},
  doi       = {10.1007/978-3-319-24177-7_16}
}
```

### huang_sok_attack_surface_device_drv_iso

**Option A: the published version.** Use this if the authors confirm that the ACSAC 2025 paper is the same work. The title changed. Built from the Crossref record.

```bibtex
@inproceedings{huang_sok_attack_surface_device_drv_iso,
  author    = {Huang, Yongzhe and Huang, Kaiming and Ennis, Matthew and Narayanan, Vikram and Burtsev, Anton and Jaeger, Trent and Tan, Gang},
  title     = {Beyond Driver Isolation - Triaging Threats against Driver Isolation},
  booktitle = {2025 IEEE Annual Computer Security Applications Conference (ACSAC)},
  year      = {2025},
  pages     = {245--261},
  publisher = {IEEE},
  doi       = {10.1109/ACSAC67867.2025.00033}
}
```

**Option B: keep the arXiv preprint, with a field set IEEEtranS prints correctly.** Built from the arXiv record.

```bibtex
@misc{huang_sok_attack_surface_device_drv_iso,
  author       = {Huang, Yongzhe and Huang, Kaiming and Ennis, Matthew and Narayanan, Vikram and Burtsev, Anton and Jaeger, Trent and Tan, Gang},
  title        = {{SoK}: Understanding the Attack Surface in Device Driver Isolation Frameworks},
  howpublished = {arXiv:2412.16754},
  year         = {2024},
  month        = dec,
  url          = {https://arxiv.org/abs/2412.16754}
}
```

## Cosmetic rendering notes

These do not change the OK/ERROR classification. They are visible in the PDF, so fix them if you want a clean bibliography.

1. **Titles are sentence-cased.** The repository's IEEEtranS.bst v1.12 converts titles to sentence case, so acronyms and proper nouns that are not braced come out lowercased. Seen in `render/test.bbl`:

   | key | renders as | fix |
   |---|---|---|
   | civscope | "Civscope" | `{CIVSCOPE}` |
   | huang_sok_attack_surface_device_drv_iso | "Sok:" | `{SoK}` |
   | hacks | "hakc" | `{HAKC}` |
   | rlbox | "firefox" | `{Firefox}` |
   | isolation-without-taxation | "webassembly and sfi" | `{WebAssembly}`, `{SFI}` |
   | daikon | "The daikon system" | `{Daikon}` |
   | wilke2020nosecuritywithoutintegrity | "Sevurity" | `{SEVurity}` |

2. **Unicode en-dash in `pages` makes IEEEtranS print "p." instead of "pp."** For example, `pages={1278–1308}` prints as "p. 1278–1308" because the style does not recognise the range. Affected: protection-info-system, microdriver+, invariant_infer_empirical_eval, daikon, dui (the corrected dui uses `--`). Replace `–` with `--`.
3. **sok-compartmentalization** has `title = {{ SoK: Software Compartmentalization }}`. The spaces inside the inner braces print as `“ SoK: Software Compartmentalization ,”`. Use `{{SoK}: Software Compartmentalization}`.
4. **lxds** has `{{LXDs} : Towards…}`, which prints "LXDs : Towards". Remove the space before the colon.
5. **`language={en}` wrappers.** The Zotero-style entries (microdriver+, daikon, invariant_infer_empirical_eval, dui) carry `language={en}`. IEEEtranS wraps them in `\BIBforeignlanguage{en}`, which is harmless but logs a hyphenation warning if babel has no `en` language.
6. **Missing DOIs.** These entries have a DOI but do not include it: isolation-without-taxation (10.1145/3498688), hardy1988confuseddeputy (10.1145/54289.871709), bulkhead (10.14722/ndss.2025.230328), nooks (10.1145/1133373.1133393), Mao11LXFI (10.1145/2043556.2043568), Ferrante87PDG (10.1145/24039.24041), LiuTJ17Ptrsplit (10.1145/3133956.3134066), wilke2020nosecuritywithoutintegrity (10.1109/SP40000.2020.00080). IEEEtranS does not print `doi` anyway.

## Raw responses (`citecheck/raw/`)

- **Crossref:** `crossref-<key>.json` for DOI lookups and `crossref-search*-<key>.json` for title searches. Also `crossref-dui-book.json` (the ESORICS 2015 Part II volume) and `crossref-huang_sok-acsac2025.json`.
- **USENIX:** `usenix-<key>.html` (presentation pages with BibTeX) and `usenix-legacy-*.html` (legacy pages with page ranges).
- **NDSS:** `ndss-*.html` and `pdf/ndss-2022-26-paper.pdf`, `pdf/ndss-2023-117-paper.pdf`, `pdf/ndss-2025-s328-paper.pdf` (bylines).
- **arXiv:** `arxiv-2412.16754.html`, `arxiv-2404.08716.html`.
- **DBLP:** `dblp-botchallenge-sample.html`, the bot-challenge page DBLP returned instead of JSON.
