# Introduction evidence: interface attacks on compartmentalized software

These notes are research material for the introduction of the InterSpec paper.

**Quote conventions**
- Quotes are verbatim from text extracted with `pdftotext`. The only changes are these:
  - Hyphens that the PDF inserted at line breaks are joined (for example, "in-memory" printed as "inmemory" is restored).
  - `[...]` marks omitted text, usually lists of citations.
  - `(sic)` marks the authors' own typos.
- "p." means the printed page number of the cited version. Where that version has no printed page numbers, a section is given instead.

**Downloaded files** are in `/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad/intro-research/dl/`. Per-page text extracts are in `/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad/intro-research/pages/`.

---

## [assess_civ] Lefeuvre, Bădoiu, Chien, Huici, Dautenhahn, Olivier. "Assessing the Impact of Interface Vulnerabilities in Compartmentalized Software." NDSS 2023. DOI 10.14722/ndss.2023.24117

**What I read:** the full text, in two versions.
- The NDSS camera-ready PDF (`dl/ndss23-117-paper.pdf`, 15 pages, with printed page numbers 1–15).
- arXiv 2212.12904v2, whose title I verified as identical (`dl/arxiv-2212.12904.pdf`). Its text matches the NDSS PDF apart from layout.

All page numbers below refer to the NDSS PDF.

**Facts**

1. ConfFuzz was applied to 25 applications and 36 compartment APIs and found 629 vulnerabilities.
   > "We apply ConfFuzz to a set of 25 popular applications and 36 possible compartment APIs, to uncover a wide data-set of 629 vulnerabilities."

   Location: Abstract, p. 1. The introduction calls the same data set "629 potential vulnerabilities" (§I, p. 2). §V-B (p. 8) says: "Overall, ConfFuzz found 629 unique bugs deduplicated from 15,371 crashes."

2. The corpus consists of 39 scenarios.
   > "Our corpus is composed of 25 applications and 36 library/module/function APIs, totaling 39 real-world sandbox and safebox scenarios."

   Location: §V-A, p. 7.

3. Several scenarios come from existing frameworks, and only 2 of those 12 frameworks protect against any CIV class.
   > "Several of these scenarios (16/39, see table) have been presented as use cases in 12 different compartmentalization frameworks, only 2 of which [42], [16] providing protection against certain CIV classes"

   Location: §V-A, p. 7. [42] is RLBox and [16] is SOAAP.

4. The CIVs are spread over both trust directions: 379 in sandbox mode and 250 in safebox mode.
   > "In the sandbox mode, [...] we found 379 CIVs. [...] In the safebox mode, the fuzzer found 250 unique crashes."

   Location: §V-B, p. 8.

5. CIVs were found in all but 3 scenarios.
   > "CIVs are widespread among unmodified applications. Indeed, all but 3 scenarios present CIVs."

   Location: §V-C, p. 8.

6. The impact is severe: write vulnerabilities are common and most read/write CIVs are arbitrary.
   > "We find that more than 75% of scenarios studied present at least one write vulnerability, and all safebox scenarios present at least one arbitrary read, which defeats attempts to protect secrets."

   > "We find that more than 70% of read and 66% of write vulnerabilities are arbitrary, as well as half of execute CIVs."

   Location: §V-E, p. 10.

   The totals in Table III (p. 7) are below. Each figure is the number of CIVs, with the arbitrary ones in parentheses.

   | Mode | Read | Write | Exec | Alloc | Null |
   |---|---|---|---|---|---|
   | Sandbox | 246 (192) | 124 (105) | 12 (5) | 24 | 195 |
   | Safebox | 154 (97) | 60 (17) | 3 (2) | 78 | 103 |

7. **Concrete example (sandbox):** ImageMagick sandboxing libghostscript under the Cali framework. A compromised library can write arbitrarily into the application through a callback.
   > "ImageMagick exposes a callback to libghostscript that allows the untrusted library to perform arbitrary writes in the application's compartment as often as it wants and at any time, negating spatial isolation entirely."

   Location: §II, p. 2 (Listing 1).

8. **Concrete example (safebox):** isolated OpenSSL keys can be extracted with a single CIV.
   > "In all cases, we are able to extract keys out of the safebox leveraging a single CIV uncovered by our fuzzer"

   Location: §V-E.1, p. 11. On p. 10 the paper notes: "We count at least 8 studies safeboxing it".

   One of the libssl CIVs gives code execution. The interface object `SSL_CTX` carries callbacks: "These callbacks are very common across the libssl API and result in arbitrary code execution." (p. 11)

9. **Real-world impact: sudo.** A CIV found in sudo's authentication API is also a real bug.
   > "This decade old issue manifests when users enter small passwords and was assigned CVE-2022-43995 after we reported it."

   Location: §V-E.2, p. 11.

10. **Real-world impact: Nginx's production privilege separation.** A compromised worker can corrupt memory in the master process.
    > "In this model we found a decade-old CIV that allows a worker to trigger memory corruption in the master"

    Location: §V-E.3, p. 11. **Caveat:** the authors also say "This particular CIV is low impact due to control constraints in the mutex unlocking routine".

11. ConfFuzz reproduced RLBox's own validation needs in the scenario RLBox used.
    > "in HTTPd with libmarkdown, a scenario from RLBox [42], ConfFuzz correctly discovered all CIVs addressed by RLBox, asserted the criticality of the bugs, and even one more due to library version differences."

    Location: §V-B, p. 8.

12. A CIV can attack a component that never talks to the compromised one ("corrupted data forwarding").
    > "The untrusted HTTP parsing library thus manages to attack libssl even though the two libraries do not directly communicate."

    Location: §V-D Pattern 3, p. 9.

13. The authors' general claim about the impact of CIVs:
    > "in many cases, CIVs seriously reduce or even fully negate all benefits of compartmentalization, and that even when the interface is extremely simple"

    Location: §I, p. 2.

14. Malicious compartments can use CIVs for data-only and control attacks.
    > "Malicious compartments can leverage a CIV to mount data and control-based attacks, confusing a victim compartment into leaking and altering its private data and addresses, executing code, etc."

    Location: §III, p. 3. The paper classifies CIVs into 3 classes with 8 subclasses (§III, p. 3).

15. Isolation alone does not bring security unless the interface data is vetted.
    > "Clearly, while a strong compartmentalization framework capable of reliably enforcing spatial and temporal isolation is necessary, it is insufficient to offer tangible security benefits: software must also be adapted to fit distrust scenarios by vetting information that crosses compartment interfaces."

    Location: end of §II, p. 3.

16. **For argument (2):** existing frameworks ignore interfaces.
    > "almost all modern compartmentalization frameworks [...] neglect the problem of securing interfaces, and rather focus on transparent and lightweight spatial separation."

    Location: §I, p. 1.

    > "The vast majority of modern compartmentalization frameworks [...] do not achieve more than basic ABI-level interface sanitization at security domain crossing, such as switching the stack and clearing registers."

    Location: §VII d, p. 13.

17. **For argument (2):** protections are partial and manual. This is the summary of the systematization of defenses.
    > "No existing compartmentalization framework tackles all CIV classes. Techniques that can address a subset of CIVs only offer partial and/or non-generic solutions. Even the most comprehensive system, RLBox [42], relies extensively on manual checking with no guarantees of check correctness."

    Location: §III-D "Summary: CIV Protections are in their Infancy", p. 4.

18. **For argument (2):** RLBox forces humans to write checks.
    > "RLBox [42] proposes to employ compiler-based techniques to force experts to write checks prior accessing interface-crossing data (and in particular indexing information). This ensures that humans will sanitize the API, but does not offer correctness guarantees."

    Location: §III-B DC2, p. 3.

    > "RLBox sanitizes sandbox data flow in a partially automated way: using static analysis and C++ type information, the framework can add certain checks automatically. When not possible, RLBox outputs compiler errors to require human intervention. [...] Both approaches are prone to human error due to manual effort."

    Location: §VII d, p. 13. "Both approaches" means RLBox and SOAAP.

19. **For argument (2):** the paper's own contribution is detection, not protection, and fixing CIVs is hard.
    > "addressing interface vulnerabilities goes beyond writing simple checks. We conclude the paper with guidelines for CIV-aware compartment interface design, and appeal for more research towards systematic CIV detection and mitigation."

    Location: Abstract, p. 1.

**Caveat for the paper's wording.** ConfFuzz fuzzes possible boundaries in monolithic software that has not been compartmentalized.
> "we propose to fuzz monolithic (non-compartmentalized) software at possible arbitrary compartment boundaries"

Location: §IV-B, p. 5.

Write "629 potential CIVs at candidate compartment boundaries", not "629 vulnerabilities in compartmentalized applications". The ImageMagick/Cali, RLBox/HTTPd, sudo and Nginx cases are the ones tied to real or published compartmentalizations.

---

## [rlbox] Narayan, Disselkoen, Garfinkel, Froyd, Rahm, Lerner, Shacham, Stefan. "Retrofitting Fine Grain Isolation in the Firefox Renderer." USENIX Security 2020, pp. 699–716

**What I read:** the full text of the USENIX proceedings PDF (`dl/rlbox-sec20-narayan.pdf`). PDF page *n* corresponds to printed page *n* + 697. The arXiv extended version 2003.00572 was also downloaded but is not cited.

**Facts**

1. Sandboxing gives a large benefit, which supports the first half of argument (1).
   > "we are migrating Firefox to an architecture that isolates these libraries in lightweight sandboxes, dramatically reducing the impact of a compromise. Retrofitting isolation can be labor-intensive, very prone to security bugs, and requires critical attention to performance."

   Location: Abstract, p. 699.

   > "once these libraries are memory isolated, the harm they can inflict is minimal. For example, an attacker that compromises an image decoding library could at worst change how images display."

   Location: §2, p. 701.

   For deployment, the sandboxed libGraphite "ships in stock Firefox 74 to Linux users and in Firefox 75 to Mac users" (§9.2, p. 715). As motivation, "an out-of-bounds write in libvorbis was used to exploit Firefox at Pwn2Own 2018" (§1, p. 699).

2. The interface can nullify the sandbox.
   > "the renderer was not built to protect itself from libraries; thus, we have to sanitize all data and regulate control flow between the library and renderer to prevent libraries from breaking out of the sandbox. In our experience, bugs at the library-renderer boundary are not only easy to overlook, but can nullify any sandboxing effort"

   Location: §1, p. 700.

3. The RLBox developers themselves introduced interface bugs.
   > "While migrating to this model we made numerous mistakes—overlooking attack vectors and discovering many bugs only after building RLBox to help detect them."

   Location: §3, p. 701.

4. **Arbitrary read/write.** A sandboxed libjpeg can turn unsanitized callback parameters into read and write gadgets.
   > "if the parameter jd of fill_input_buffer() is not sanitized (line 35), the read of jd->src on line 36 becomes an arbitrary-read gadget. In the same callback, if both jd and src are unsanitized, the write to src->next_input_byte on line 39 becomes an arbitrary-write gadget."

   Location: §3.1, p. 702.

5. **Code execution.** A pointer leak combined with a write gadget allows code execution.
   > "Leaking pointers from the Firefox renderer to the sandboxed libjpeg can allow an attacker to derandomize ASLR [50] or otherwise learn locations of code pointers (e.g., C++ virtual tables). Together with an arbitrary-write gadget, this can allow an attacker-controlled libjpeg to execute arbitrary code in the renderer."

   Location: §3.1, p. 702.

6. **Double fetch.**
   > "In a concurrent libjpeg sandbox thread, an attacker can modify mInfo.output_scanline after the check (line 16), and before the value is fetched (again) and used on line 18. This would bypasses (sic) the bounds check, leading to an arbitrary-write gadget."

   Location: §3.1, p. 703.

7. **Control-flow hijacking** through corrupted callback state and unexpected callback invocation.
   > "Failing to sanitize client_data before using it allows an attacker to set the pointer to a maliciously crafted object and hijack control flow when Firefox invokes a virtual method on this object."

   > "If an attacker invokes my_error_exit() before setjmp_buffer is initialized, they can (again) hijack the renderer control flow."

   Location: §3.2, p. 703. The callback-state-exchange attack in the same section leads to a "data race and use-after-free vulnerability" (p. 703).

8. **For argument (2):** checking by hand is error prone.
   > "Modifying the Firefox JPEG decoder to guard against all the attacks discussed in Section 3 requires substantial code additions and modifications. Doing this manually is extremely error prone."

   Location: §4, p. 703.

9. **For argument (2):** validators are written by hand and assumed to be correct.
   > "The protections offered by RLBox are only valid if the Firefox code that interfaces with the sandboxed library code is retrofitted to account for untrusted code running in the library sandbox. As we discuss next, this is usually notoriously difficult to get right. RLBox precisely reduces this burden to writing a series of validation functions. In our attacker model, we assume these functions to be correct."

   Location: §2, p. 701.

   > "Unfortunately, it is still up to the user to get these checks correct; RLBox just makes this task easier."

   Location: §4.3, p. 705.

10. **For argument (2), with numbers:** the validators are the manual, hardest part.
    > "Finally, RLBox identifies the (100) sites where we must validate tainted data (§4.3). Though RLBox cannot automate the validators, we find that we only need 35 unique validators—all less than 4 lines of code. In practice, we found this to be the hardest part of migration since it requires understanding the domain-specific invariants."

    Location: §7.3, p. 711.

    The breakdown comes from Figure 3, p. 711, across 6 libraries:

    | Library | Validator sites | Unique validators | Average LOC |
    |---|---|---|---|
    | JPEG | 28 | 11 | 3 |
    | PNG | 51 | 14 | 4 |
    | GZIP | 10 | 3 | 2 |
    | Theora | 5 | 3 | 3 |
    | VPX | 2 | 2 | 2 |
    | OGG-Vorbis | 4 | 2 | 2 |

    On average, sandboxing one library "takes a bit over two days [...] and roughly 180 LOC (25% code increase)" (§7.3, p. 710).

11. **What RLBox *does* automate:** pointer swizzling, pointer bounds checks and marshaling. This partly qualifies argument (2).
    > "RLBox automatically swizzles pointers [...] manually identifying the 297 locations where the application interacts with such pointers would have been tedious and error-prone. Third, RLBox automatically performs bounds checks (§4.2); the number of required pointer bounds checks that were automatically performed by RLBox are again in the hundreds (138)."

    Location: §7.3, p. 711.

12. Double fetches are only partly handled.
    > "While RLBox provides APIs to assist with double-fetches, the possibility of unhandled double-fetch bugs still remain."

    Location: §8, p. 714.

---

## [huang_sok_attack_surface_device_drv_iso] Huang, Huang, Ennis, Narayanan, Burtsev, Jaeger, Tan. "SoK: Understanding the Attack Surface in Device Driver Isolation Frameworks." arXiv 2412.16754v1 (21 Dec 2024)

**What I read:** the full text of arXiv v1, which is the only arXiv version, with printed page numbers 1–18.

**Bibliography note:** a web search (snippet only) shows this work was published as "SoK: Beyond Driver Isolation – Triaging Threats against Driver Isolation", ACSAC 2025, by the same authors. I could not read that version because its hosts were blocked, so the facts below are from arXiv v1. Consider updating the bibliography entry.

**Facts**

1. The SoK quantifies CIVs over 11 drivers from 7 driver classes.
   > "different classes of CIVs are prevalent across the studied drivers under a baseline threat model, with large drivers having more than 100 instances of different CIVs and an average of 33 instances across the studied drivers. Enforcing extra security properties, such as CFI, can reduce the number of CIVs to around 28 instances on average."

   Location: Abstract, p. 1.

   > "we select 11 drivers (Table 6) from 7 different driver classes"

   Location: §7, p. 11.

2. A compromised driver can still attack the kernel through the interface.
   > "Malicious drivers may still compromise kernel compartments by exploiting the isolation interface, as demonstrated by Lefeuvre et al. [36] in compartmentalized user-space applications."

   Location: §1, p. 1.

   > "even after isolation, a compromised or malicious driver can attack the kernel by misusing the kernel/driver interface."

   Location: §5, p. 6.

3. **Concrete example (arbitrary R/W):** corrupting the type selector of a tagged union in the acpi_power_meter driver.
   > "By crafting the integer struct's value field with a specific address and corrupting the type field, the malicious driver can trick the kernel into performing read/write operations at arbitrary memory locations via the value field."

   Location: §5.2.2, p. 7 (Listing 1).

   The mgag200 driver case allows "a buffer overflow vulnerability" through a corrupted loop condition (p. 7, Listing 2).

4. The static results were validated in two ways: manual review (90% precision) and PoCs (60–100% success).
   > "Our manual validation reveals that the taint analysis achieves a high level of accuracy, with a precision of 90% across the evaluated cases."

   > "for a large percentage of instances (60 to 100%) we could construct successful exploits."

   Location: §7.1, pp. 12–13.

   **Caveat:** the PoCs are small reproductions, not full-system exploits against a particular framework. The authors write: "For each instance, we manually constructed two programs: K' (relevant kernel code snippet) and D' (attack code for the kernel-driver interface)." (p. 12)

5. Frameworks enforce isolation (P1, P4) but rarely enforce interface data integrity (P3).
   > "almost all driver isolation projects enforce P1 and P4. [...] However, P3 is rarely enforced, with only a few projects [7], [45] partially enforcing this property through checks at domain crossings, mainly due to the difficulty of inferring data invariants for integrity checks."

   Location: §4, Summary, p. 6. [7] is Butt et al. (ACSAC 2009) and [45] is LXFI.

   In Table 2 (p. 5), 18 frameworks from 2002–2023 are compared. The text (p. 2) says "we have identified 20 most impactful projects", but Table 2 lists 18 rows.

6. **For argument (2):** inferring and validating invariants of interface data is called unsolved.
   > "we do not assume a defense that infers and validates invariants of interface data, which is an unsolved problem."

   Location: §6.1, p. 8.

   > "Previous work by Butt et al. [7] utilized data invariants to enforce P3, which can be developed manually or through automated methods [17]. However, ensuring soundness and completeness of data invariant inference in practice is challenging."

   Location: §7.2, p. 13. [17] is Daikon.

7. **For argument (2):** most frameworks do not address CIVs.
   > "most existing driver isolation frameworks do not address CIVs, as illustrated in Section 3.5, where security properties that address the misuse of interfaces and shared data, such as P3 and P5, are not widely enforced."

   Location: §5, p. 6.

8. **Prior automated work (a contradiction to argument 2; see the final section).**
   > "an extension to the Microdriver architecture by Butt et al. [7] infers and checks data invariants during domain crossings using the dynamic invariants inference tool Daikon [17]."

   Location: §4.3, p. 5.

   > "LXFI addresses this with API integrity via developer-supplied annotations for P3"

   Location: §4.1, p. 4.

9. Driver code is a large attack surface.
   > "making up 16–59% of all reported Linux kernel vulnerabilities since 2014 (Table 1)."

   Location: §1, p. 1.

10. The authors consider interface hardening feasible, which supports InterSpec's premise.
    > "We believe these lower numbers suggest that effective defense against CIVs is possible without imposing drastic changes to the interface."

    Location: §8 L2, p. 14.

---

## [civscope] Chien, Bădoiu, Yang, Huo, Kaoudis, Lefeuvre, Olivier, Dautenhahn. "CIVSCOPE: Analyzing Potential Memory Corruption Bugs in Compartment Interfaces." KISV '23, Koblenz, pp. 33–40. DOI 10.1145/3625275.3625399

**What I read:** the full text of the NSF PAR copy (`dl/civscope-par.pdf`, printed pp. 33–40). The work is not on arXiv.

**Facts**

1. CIVScope is a static taint analysis over the Linux kernel, and it finds too many paths to fix by hand.
   > "We find that there are many compartment bypassing paths (395/4394 driver interfaces have 22741 paths), making it impossible to correct by hand."

   Location: Abstract, p. 33.

2. **Concrete example (privilege escalation via a confused deputy).** The paper illustrates it with a hand-written exploit in Figure 1.
   > "Leveraging the exported trace interface (as depicted in Figure 1), trace_parser_get_init, a malicious device driver can forge a pointer to the task_struct object and ask trace_parser_get_init to set the uid to 0 on behalf of the interface. Since the ftrace system has the authority to access any object inside the core kernel, any driver can get root privilege and escalate through this confused deputy interface."

   Location: §1, p. 34.

   **Caveat:** the authors call this a hypothetical boundary choice: "this example clearly makes a poor choice by including the tracing system into the core kernel".

3. Numbers for the core kernel and for drivers.
   > "the core linux kernel exposes 648 interfaces, with 68 having a CMDP. These 68 interfaces contribute to a total of 24,900 unconditioned paths out of 50,300 paths, which is nearly 49.5% of paths being directly exploitable."

   > "Drivers expose 395 CMDP interfaces out of a total of 4,394. The 395 interfaces account for a total of 19,555 out of 42,379, nearly 46.1% of which are unconditioned."

   Location: §1, p. 34.

   **Inconsistency:** the abstract says 22,741 paths for the 395 driver interfaces, while §1 says 19,555 of 42,379. If you cite a count, cite the "395 of 4,394 driver interfaces" figure, which agrees in both places.

4. Prior protections are type-system based (and do not fit unsafe code) or are dynamic detectors.
   > "One solution is to use the type system to automatically prevent classes of CIVs [18] [14], but they neglect a wide range of software written in unsafe languages (e.g. operating systems, hypervisors, etc.). Recent work uses dynamic analysis on unsafe code [5, 10], but fall short for broader generalizations."

   Location: §1, p. 33. [18] is RLBox, and [5, 10] are DUI and ConfFuzz.

5. **For argument (2):**
   > "we discovered that 68 out of 648 exposed interfaces have data flows bypassing the compartment boundaries. This finding highlights the impracticality of manually securing the CMDP."

   Location: §6 Conclusion, p. 39.

   On ConfFuzz, CIVScope's related work says it leaves a "high manual effort from the developer to analyze and fix identified CIVs" (§7 Related Work, p. 39).

---

## [dui] Hu, Chua, Liang, Saxena. "Identifying Arbitrary Memory Access Vulnerabilities in Privilege-Separated Software." ESORICS 2015, LNCS 9327

**What I read:** the full text of the authors' copy (`dl/dui-esorics15.pdf`, from comp.nus.edu.sg, 19 pages). This copy has no printed proceedings page numbers, so locations are sections.

**Bibliography:** the author order (Hong Hu, Zheng Leong Chua, Zhenkai Liang, Prateek Saxena) is verified from the PDF. The pages, pp. 312–331, come from search snippets only (pure.psu.edu and the Springer listing).

**Facts**

1. Interfaces let one partition influence memory accesses in another.
   > "However, the interfaces still provide a channel for one partition to influence code in other partitions. As a result, certain memory access patterns can be leveraged by attackers to perform arbitrary memory access. We refer to this type of memory access errors by the acronym DUI (Dereference Under the Influence)."

   Location: Abstract.

2. Adding the right checks is hard, both manually and automatically.
   > "Unfortunately, it is non-trivial to ensure that adequate checking code has been added at correct locations. [...] manual modification usually takes a long time to fully understand the requirement of checking operations, while automatic separation methods often miss important checks."

   Location: §1, "Challenges".

3. The tool is DUI Detector, which uses binary analysis, symbolic analysis and dynamic taint. The paper presents 4 case studies.
   > "We present four case studies where attackers can perform DUI attacks."

   Location: §1.

   The case studies are in §5.1:
   - Three cover a malicious kernel attacking a protected user program: glibc `malloc`/`brk` (a write DUI), glibc `mmap2`, and `cat` via `read`/`write`.
   - One covers a malicious library: libsdl under Codejail.

4. **Concrete example (arbitrary write by a sandboxed library):**
   > "A malicious SDL library can exploit this DUI vulnerability to corrupt any memory location of the main code, even if the main program is protected by memory isolation schemes."

   Location: §5.1, "Library Isolation".

   **Caveat:** this case uses a small test program the authors wrote ("We write a simple program that requests a screen object from the SDL library").

5. The authors' conclusion:
   > "Simple memory isolation is inadequate to prevent unauthorized memory access. [...] DUI vulnerabilities inside the protected partition still allow other partitions to access arbitrary protected memory."

   Location: §5.3.

6. Detection only: the fix is left to developers.
   > "Once a DUI vulnerability has been identified, developers can mitigate the consequences of the vulnerability by introducing proper checks to the vulnerable code."

   Location: §6 Discussion, "Defense".

**Note:** the DUI paper does **not** attack OpenSSH. It cites OpenSSH's privilege separation only as a motivating example (§1).

---

## [microdriver+] Butt, Ganapathy, Swift, Chang. "Protecting Commodity Operating System Kernels from Vulnerable Device Drivers." ACSAC 2009, pp. 301–310

**What I read:** snippets only. All full-text hosts were blocked by the proxy: csa.iisc.ac.in, scail.cs.wisc.edu, pages.cs.wisc.edu and the Rutgers repository. The pages come from Huang SoK reference [7]. The DOI 10.1109/ACSAC.2009.35 comes from a search snippet.

**Facts**

1. **[secondary source, full text read]** The work infers and checks interface data invariants with Daikon.
   > "an extension to the Microdriver architecture by Butt et al. [7] infers and checks data invariants during domain crossings using the dynamic invariants inference tool Daikon [17]."

   Location: Huang SoK §4.3, p. 5.

   Huang SoK Table 2 (p. 5) lists it as "User-mode + Daikon" under the "Exploitable" threat model.

2. **[snippet only]** Its architecture, as paraphrased from the abstract in search results:
   - Each driver is split into a small trusted kernel-mode part and an untrusted user-mode part.
   - "A RPC monitor mediates all control and data transfers between the kernel- and user-mode components."
   - The monitor checks that data from the user-mode part preserves kernel data structure integrity.
   - The paper presents "a runtime technique to automatically infer such integrity specifications."
   - The authors report that the Linux prototype "can prevent compromised device drivers from affecting the integrity of kernel data" without hurting common-case performance.

   **Verify these against the paper before quoting.**

**Implication:** this is the closest prior work to InterSpec's "automatic inference and enforcement of interface data policies". See "Contradictions" below.

---

## [sok-compartmentalization] Lefeuvre, Dautenhahn, Chisnall, Olivier. "SoK: Software Compartmentalization." IEEE S&P 2025

**What I read:** the full text of arXiv 2410.08434v1, the only arXiv version, with printed page numbers 1–20. Its arXiv comment reads "Accepted to appear in the 46th IEEE Symposium on Security and Privacy (S&P'25)".

**Facts**

1. Interface safety is defined as a key problem.
   > "A key problem of compartmentalization is validating all control and data flows at compartment boundaries [198]; we refer to this as ensuring interface safety. Improper validation results, among others, in confused deputy vulnerabilities [123] well-studied in previous works [84, 88, 129, 160, 181]."

   Location: §2, p. 2. The cited works are Iago, CIVScope, DUI, ConfFuzz and RLBox.

2. **Both halves of argument (1)**, drawn from deployed software:
   > "Separation is effective but vulnerable. Concrete impact on bug exploitability has been documented where compartmentalization was pushed to production – most of Table 4. In the OpenBSD userland, the OpenSSH and slaacd sandbox compartments successfully mitigated code-execution flaws [3, 4, 19, 41]. Similar observations were made for Nginx workers [5, 6], and web browser site isolation. Still, the protection is not limitless: interface safety vulnerabilities were reported against OpenSSH [17, 39, 40], Firefox [144, 218], Nginx [7], Chrome and generally site isolation [16]."

   Location: §4, p. 12.

   The cited items include:
   - [17] "CVE-2006-5794: Sandbox escape via auth bypass in OpenSSH"
   - [39], [40] OpenSSH 7.0 and 7.4 "Fixing Sandbox Escape"
   - [7] CVE-2016-1247
   - [16] "Chrome: Site Isolation bypass via NavigationPreloadRequest"

3. Research mostly ignores interface safety.
   > "Although some works in §3 are concerned with the problem of interface safety, most scope it out to focus on performance. [...] should compartmentalization become widespread, interface safety flaws will be the main vulnerabilities of tomorrow."

   Location: §4, p. 12.

4. **For argument (2):** abstractions treat interface safety as someone else's problem.
   > "Although interface safety is a key problem of compartmentalization, most abstractions consider it orthogonal to their mission (Table 2)."

   > "Insight 9: There is a widespread misconception that interface safety is orthogonal to the mission of compartmentalization abstractions. More work is needed on abstractions that contribute to compartment-interface hardening."

   Location: §3.2, "Compartment-Interface Hardening", p. 8.

   The same paragraph lists existing hardening: "forcing the presence of checks on interface-crossing data, forcing users to write checks [181], or checking automatically when possible [165, 172, 181]". The references are [181] RLBox, [165] Glamdring and [172] LXFI. **This is the SoK's own pointer to prior automatic checking; see Contradictions.**

5. **For argument (2):** securing interfaces is left to developers, and the SoK calls for automation.
   > "most of the works described in §3.2 leave the job of securing internal and external interfaces, a complex and particularly error-prone task, entirely to the developer."

   Location: §5, Challenge 2, p. 13.

   > "for more automated interface safety checking methods; and for more fuzzing targeted at the needs of compartmentalization."

   Location: §5, Challenge 2, p. 14.

6. Threat models assume hardened interfaces, and that assumption does not hold.
   > "Compartmentalization works largely make assumptions about interfaces (adequately hardened, free of high-level logic bugs) [...] These assumptions do not hold in practice. Interfaces are porous and abstractions must be involved to ensure safety by construction [91, 160, 213] (§3.2)."

   Location: §5, Challenge 3, p. 14.

7. Scope of the SoK: "a systematic study of 211 software compartmentalization works and 61 deployed approaches" (§7 Conclusion, p. 14).

---

## Optional classic references (not yet in the bibliography)

### Chen, Xu, Sezer, Gauriar, Iyer. "Non-Control-Data Attacks Are Realistic Threats." 14th USENIX Security Symposium, Baltimore, MD, July 2005

**Bibliography sources:**
- The authors are taken from the paper PDF on www.usenix.org (`dl/chen05.pdf`).
- The venue, city and month come from the USENIX page's BibTeX. That BibTeX lists only the first 3 authors, but the PDF lists 5.
- Proceedings page numbers are **not verified**, so leave them out or check them elsewhere.

**Fact:**
> "We demonstrate that many real-world applications, including FTP, SSH, Telnet, and HTTP servers, are vulnerable to such attacks. In each case, the generated attack results in a security compromise equivalent to that due to the control-data attack exploiting the same security bug."

Location: Abstract.

### Hu, Shinde, Adrian, Chua, Saxena, Liang. "Data-Oriented Programming: On the Expressiveness of Non-Control Data Attacks." IEEE S&P 2016, pp. 969–986

**Bibliography sources:**
- The authors come from the NUS author copy (`dl/dop-tc.pdf`).
- The pages come from reference [7] of Cheng et al., arXiv 1902.08359, and agree with search snippets.
- The DOI 10.1109/SP.2016.62 is from a snippet only.

**Fact:**
> "In this paper we show that such attacks are Turing-complete. [...] 8 out of 9 real-world programs have gadgets to simulate arbitrary computations and 2 of them are confirmed to be able to build Turing-complete attacks."

Location: Abstract of the NUS author copy, which is titled as the conference paper.

### Checkoway, Shacham. "Iago attacks: Why the system call API is a bad untrusted RPC interface." ASPLOS '13, pp. 253–264

The bibliographic data is verbatim from Huang SoK reference [11]. This is the classic case of a malicious kernel attacking a protected application through system-call return values. ConfFuzz calls Iago vulnerabilities "CIVs at the system-call boundary" (§III, p. 3).

---

## Best evidence for the introduction

### Argument (1): isolation helps, but the interface data is an attack vector

**First half (isolation is a real improvement):**
- **[sok-compartmentalization]** §4, p. 12: "the OpenSSH and slaacd sandbox compartments successfully mitigated code-execution flaws".
- **[rlbox]** p. 701: "once these libraries are memory isolated, the harm they can inflict is minimal". The sandboxing ships in Firefox 74/75 (p. 715).

**Second half, ranked by strength:**

1. **[assess_civ]** ConfFuzz found 629 (potential) CIVs in 39 sandbox and safebox scenarios over 25 applications and 36 APIs.
   - All but 3 scenarios had CIVs.
   - More than 75% of scenarios had at least one write CIV.
   - More than 70% of read CIVs and 66% of write CIVs were arbitrary.
   - Concrete cases:
     - Keys were extracted from a safeboxed OpenSSL with a single CIV.
     - libghostscript, sandboxed by Cali, gets arbitrary writes into ImageMagick via a callback, "negating spatial isolation entirely".
     - A decade-old memory corruption in Nginx's production master/worker separation.

   Locations: Abstract and pp. 2, 7, 8, 10, 11.

2. **[rlbox]** In Firefox, a compromised sandboxed libjpeg could do the following without escaping the sandbox:
   - turn unsanitized callback arguments into arbitrary-read and arbitrary-write gadgets;
   - combine leaked pointers with a write gadget to "execute arbitrary code in the renderer";
   - defeat bounds checks via double fetches;
   - hijack control flow via a corrupted `client_data` or an early `longjmp`.

   The RLBox authors "made numerous mistakes" at this interface themselves. Locations: §3, pp. 701–703.

3. **[huang_sok_attack_surface_device_drv_iso]** At the kernel/driver interface of 11 Linux drivers, there are on average 33 CIV instances per driver, and more than 100 in large drivers. 60–100% of the sampled instances were turned into working PoCs (snippet-level). One example is a type-confused ACPI union that gives arbitrary kernel read/write. Locations: Abstract and pp. 7, 12–13.

4. **[dui]** A malicious SDL library isolated with Codejail can "corrupt any memory location of the main code". The authors conclude that "Simple memory isolation is inadequate to prevent unauthorized memory access." Location: §5.1, §5.3.

5. **[civscope]** A malicious driver can use the exported ftrace interface `trace_parser_get_init` to set its task's uid to 0, a confused-deputy privilege escalation. 68 of 648 core-kernel interfaces have such flows. Location: §1, p. 34. This example is illustrative and hypothetical.

### Argument (2): prior work understands the attack surface but does not automatically protect it

**Contributions to understanding the attack surface:**

| Work | Method | Scope | Location |
|---|---|---|---|
| DUI Detector [dui], 2015 | binary analysis plus symbolic execution | 4 case studies | §1, §5 |
| ConfFuzz [assess_civ], 2023 | taxonomy of 3 classes / 8 subclasses, plus fuzzing | 629 CIVs; prior defenses systematized in Table I | pp. 3–4, 8 |
| CIVScope [civscope], 2023 | static taint analysis | Linux kernel | p. 33 |
| Huang et al. SoK, 2024 | extended taxonomy plus static quantification | 11 drivers; P1–P6 properties of 18 frameworks | pp. 5–13 |
| Lefeuvre et al. SoK [sok-compartmentalization], 2025 | systematization | interface safety as a key problem | pp. 2, 8 |

**The strongest "no automated protection" statements:**

1. **[assess_civ]** §III-D, p. 4: "No existing compartmentalization framework tackles all CIV classes. [...] Even the most comprehensive system, RLBox [42], relies extensively on manual checking with no guarantees of check correctness."
2. **[rlbox]** §7.3, p. 711: "Though RLBox cannot automate the validators, [...] we found this to be the hardest part of migration since it requires understanding the domain-specific invariants". The port needed 100 validation sites and 35 hand-written validators. Section §2, p. 701 adds that "we assume these functions to be correct."
3. **[huang_sok_attack_surface_device_drv_iso]** §6.1, p. 8: "a defense that infers and validates invariants of interface data, which is an unsolved problem". Section §4, p. 6 adds that P3 (interface data integrity) "is rarely enforced [...] mainly due to the difficulty of inferring data invariants for integrity checks."
4. **[sok-compartmentalization]** §5 Challenge 2, pp. 13–14: securing interfaces is left "entirely to the developer", and research needs "more automated interface safety checking methods". This is supported by Insight 9 (p. 8).
5. **[civscope]** p. 33 says the paths are "impossible to correct by hand". **[dui]** §6 leaves the fix to developers.

---

## Contradictions and caveats to address in the paper

These items contradict a plain claim that there is "no automated protection of interface data".

1. **Butt et al., ACSAC 2009 [microdriver+], already in the bibliography.** This is the main counterexample. It **automatically infers** data-structure integrity invariants with Daikon and **enforces** them in an RPC monitor when data crosses from an untrusted user-mode driver into the kernel. In other words, it automatically infers and enforces policies on interface data. I read it from snippets only, plus Huang SoK p. 5.

   Huang SoK still treats the problem as open:
   - Butt et al. only "partially" enforce P3 (p. 6).
   - "ensuring soundness and completeness of data invariant inference in practice is challenging" (p. 13).
   - The general problem is "unsolved" (p. 8).

   **Suggested framing:** "Butt et al. infer likely invariants dynamically (Daikon) for a single interface type (kernel/user-mode driver RPC) to protect kernel data-structure integrity; no general, sound approach exists for arbitrary compartment interfaces." Before stating its limits, verify them in the paper; I could not read it.

2. **Glamdring** (Lind et al., USENIX ATC 2017, pp. 285–298; not in the bibliography; full text read in `dl/glamdring-atc17.pdf`).
   > "Glamdring enforces the invariants assumed by the static analysis at runtime. It does this by extracting invariants from the analysis phase and adding them as runtime checks in the code generation phase. Glamdring applies checks on global variables and parameters passed into and out of ecalls and ocalls."

   Location: §4.2, "Code hardening", p. 291. It also adds automatic pointer-provenance checks on pointers passed into the enclave (same page).

   This is automated interface hardening, but its scope is narrow:
   - It targets SGX enclave partitioning.
   - It checks only the invariants its own partitioning analysis relies on.
   - Its goal is to protect data the developer has annotated as sensitive.

   The compartmentalization SoK cites it as "checking automatically when possible [165, ...]" (p. 8).

3. **LXFI** (Mao et al., SOSP 2011; "Software fault isolation with API integrity and multi-principal modules", per SoK reference [172]). It enforces interface integrity automatically, but from **developer-supplied annotations** (Huang SoK p. 4). So enforcement is automated, but the policy is written by hand.

4. **RLBox itself is partially automated.** It automatically applies:
   - 138 pointer bounds checks;
   - 297 swizzle locations;
   - marshaling;
   - copy-and-verify for some types (p. 711);
   - "automatic validity checking and copy, for the types that allow it (e.g., strings)" (ConfFuzz p. 4).

   Only the semantic validators are manual. Phrase this as "RLBox automates memory-safety plumbing but leaves semantic validation to developers."

5. **KSplit and Microdrivers** automatically compute which struct fields must be shared (selective copying). This reduces oversharing, a data-leakage CIV, but does not check integrity (Huang SoK pp. 5, 11).

6. **A very recent work-in-progress:** Hu, Sun, Olivier, "Compartmentalization-Aware Automated Program Repair", arXiv 2603.09544 (10 Mar 2026), accepted to ICSE's Journal Ahead Workshop (JAWs) 2026. Full text read: `dl/arxiv-2603.09544.pdf`. It uses an LLM to generate patches for CIVs found by fuzzing. It is validated only "over a sample interface vulnerability" (Abstract, p. 1), so this is LLM repair evaluated on one CIV. Mention it if the paper claims there is no automated CIV fixing at all.

7. **Wording caveats.**
   - ConfFuzz's 629 are potential CIVs at candidate boundaries of software that was *not* compartmentalized.
   - Huang's PoCs are reproductions on kernel snippets.
   - CIVScope's ftrace example is hypothetical, and its path counts are internally inconsistent: 22,741 in the abstract versus 19,555 of 42,379 in §1.
   - DUI's case studies use test programs written by the authors.
   - DUI does not attack OpenSSH.

**Recommended claim for argument (2):** "Prior work has studied, taxonomized and detected interface vulnerabilities. Existing protections either rely on developer-written validators or annotations (RLBox, LXFI), or are limited to dynamically inferred likely invariants for one interface type (Butt et al.) or to invariants needed by a specific partitioning analysis (Glamdring). No approach automatically infers and enforces interface-data policies for arbitrary compartment interfaces."
