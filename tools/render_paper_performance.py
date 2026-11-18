#!/usr/bin/env python3
"""The numbers of the paper's performance subsection, from the raw samples
(tracker item R7).

Usage: render_paper_performance.py CAMPAIGN OUT
CAMPAIGN is the stored output of one complete re-measurement
(evaluation/results/tracker/R1/04-campaign-<commit>). Reads its p2, p3, p4,
p7, instr, p6-ports, p6-apps and r3 directories and writes to OUT: perf_rows.tex (the rows of the performance table),
policy_rows.tex (the rows of the per-policy table) and NUMBERS.md (every number
in a form that can be compared with the text). Nothing is typed in by hand: a
row exists only if its samples do.

Estimator as everywhere in this repository: the value of a variant in a
repetition is the sum of its slices (time) or the mean of its windows
(throughput); a comparison is the median over the 15 repetitions of the paired
ratio, with the smallest and the largest ratio. For a throughput the ratio is
that of the times per operation (baseline throughput over throughput), so that
every row is an overhead in time; the reports of the memcached and nginx tools
give the throughput loss instead (1 - throughput / baseline throughput), which
is smaller in magnitude for large differences. A geometric mean is taken over
the ratios (1 + overhead), not over the percentages.
"""
import collections
import csv
import json
import math
import statistics as st
import sys
from pathlib import Path

CAMP, out = Path(sys.argv[1]), Path(sys.argv[2])
WORKLOADS = json.loads((Path(__file__).resolve().parent.parent /
                        "evaluation/performance/port_workloads.json").read_text())["boundaries"]
out.mkdir(parents=True, exist_ok=True)
notes = []


def triple(ratios):
    """Overheads in percent: median, smallest, largest."""
    assert len(ratios) == 15, len(ratios)
    return tuple(100 * (f(ratios) - 1) for f in (st.median, min, max))


def tex(value, digits=1):
    text = f"{abs(value):.{digits}f}"
    if float(text) == 0:
        return text
    return ("$-$" if value < 0 else "") + text


def sliced(directory, base="rlbox-only", other="interspec"):
    """Totals per (repetition, configuration) of a sliced timing run."""
    total = collections.defaultdict(float)
    for r in csv.DictReader((directory / "samples.csv").open()):
        total[(int(r["repetition"]), r["configuration"])] += int(r["elapsed_ns"])
    reps = sorted({k[0] for k in total})
    medians = {c: st.median(total[(i, c)] for i in reps) for c in {k[1] for k in total}}
    return total, reps, medians


def instructions(directory, key="interspec"):
    summary = json.loads((directory / "summary.json").read_text())
    if "configurations" in summary:
        return summary["configurations"][key]["against_rlbox_only_percent"], summary["configurations"]
    return None, summary


perf = []  # (group, boundary, workload, metric, native, rlbox, interspec, (d, lo, hi), instr or None, format)


def port_row(group, directory, instr_dir, boundary, name, workload, metric, unit_ns, digits):
    total, reps, medians = sliced(directory)
    run = json.loads((directory / "run.json").read_text())
    per = run["rounds"] * WORKLOADS[boundary]["iterations"] * unit_ns
    d = triple([total[(i, "interspec")] / total[(i, "rlbox-only")] for i in reps])
    sandbox = triple([total[(i, "rlbox-only")] / total[(i, "native")] for i in reps])
    ins, configs = instructions(instr_dir)
    perf.append((group, name, workload, metric, medians["native"] / per, medians["rlbox-only"] / per,
                 medians["interspec"] / per, d, ins, digits))
    spread = max(c["largest_difference_between_repeats"] for c in configs.values()) \
        if "largest_difference_between_repeats" in next(iter(configs.values())) else "n/a"
    notes.append(f"- {name}, {workload}: RLBox-only against native {sandbox[0]:+.1f}% "
                 f"({sandbox[1]:+.1f} to {sandbox[2]:+.1f}); instructions per iteration "
                 f"native {configs['native']['instructions_per_iteration']:,.1f}, "
                 f"RLBox-only {configs['rlbox-only']['instructions_per_iteration']:,.1f}, "
                 f"InterSpec {configs['interspec']['instructions_per_iteration']:,.1f} ({ins:+.2f}%); "
                 f"largest difference between repeated counts {spread}")


# --- complete applications -------------------------------------------------
rows = list(csv.DictReader((CAMP / "p2/report/all-samples.csv").open()))
value = {(r["scenario"], int(r["repetition"]), r["variant"]): float(r["ops_per_s"]) for r in rows}
memcached_all = {}
for scenario in dict.fromkeys(r["scenario"] for r in rows):
    reps = sorted({k[1] for k in value if k[0] == scenario})
    d = triple([value[(scenario, i, "rlbox-only")] / value[(scenario, i, "interspec")] for i in reps])
    sandbox = triple([value[(scenario, i, "native")] / value[(scenario, i, "rlbox-only")] for i in reps])
    med = {v: st.median(value[(scenario, i, v)] for i in reps) / 1000 for v in ("native", "rlbox-only", "interspec")}
    memcached_all[scenario] = (med, d, sandbox)
    notes.append(f"- memcached {scenario}: Kops/s native {med['native']:.1f}, RLBox-only {med['rlbox-only']:.1f}, "
                 f"InterSpec {med['interspec']:.1f}; InterSpec against RLBox-only {d[0]:+.1f}% "
                 f"({d[1]:+.1f} to {d[2]:+.1f}); RLBox-only against native {sandbox[0]:+.1f}%")
# The plain GET/SET loads never call bipbuffer on the request path (log_worker_written is 0 in every
# sample); one of them is shown as the idle case, next to the two loads with a log watcher.
for scenario, label in (("balanced_8c", "8 clients, no log watcher"), ("watch_light", "1 client, log watcher"),
                        ("watch_moderate", "2 clients, log watcher")):
    med, d, _ = memcached_all[scenario]
    perf.append(("app", "memcached/bipbuffer", label, "Kops/s", med["native"], med["rlbox-only"],
                 med["interspec"], d, None, 1))

samples = list(csv.DictReader((CAMP / "p3/run/timing/samples.csv").open()))
rate = {(int(r["threads"]), int(r["repetition"]), r["variant"]): float(r["requests_per_s"]) for r in samples}
for threads in sorted({k[0] for k in rate}):
    reps = sorted({k[1] for k in rate if k[0] == threads})
    med = {v: st.median(rate[(threads, i, v)] for i in reps) / 1000 for v in ("native", "rlbox-only", "interspec")}
    d = triple([rate[(threads, i, "rlbox-only")] / rate[(threads, i, "interspec")] for i in reps])
    sandbox = triple([rate[(threads, i, "native")] / rate[(threads, i, "rlbox-only")] for i in reps])
    perf.append(("app", "nginx/libpcre", f"wrk, {threads} threads", "Kreq/s", med["native"], med["rlbox-only"],
                 med["interspec"], d, None, 1))
    notes.append(f"- nginx {threads} threads: RLBox-only against native {sandbox[0]:+.1f}% "
                 f"({sandbox[1]:+.1f} to {sandbox[2]:+.1f}) time per request; "
                 f"{100 * (1 - med['rlbox-only'] / med['native']):.1f}% fewer requests per second (ratio of medians)")

by = collections.defaultdict(dict)
for r in csv.DictReader((CAMP / "p4/run/rsync-performance.csv").open()):
    by[(r["workload"], int(r["repetition"]))][r["mode"]] = float(r["total_ns"])
rsync_ins = json.loads((CAMP / "r3/rsync/run/summary.json").read_text())["workloads"]
for workload, label in (("file_sync_194mb", "194\\,MiB file sync"), ("option_parse", "Option parsing")):
    reps = [v for k, v in by.items() if k[0] == workload]
    d = triple([v["extended_sp3"] / v["rlbox_only"] for v in reps])
    sandbox = triple([v["rlbox_only"] / v["native"] for v in reps])
    med = {m: st.median(v[m] for v in reps) for m in ("native", "rlbox_only", "extended_sp3")}
    ins = rsync_ins[workload]
    notes.append(f"- rsync {workload}: ms native {med['native'] / 1e6:.3f}, RLBox-only {med['rlbox_only'] / 1e6:.3f}, "
                 f"InterSpec {med['extended_sp3'] / 1e6:.3f}; {d[0]:+.1f}% ({d[1]:+.1f} to {d[2]:+.1f}); "
                 f"RLBox-only against native {sandbox[0]:+.1f}%; instructions of the whole run: " +
                 ", ".join(f"{n} {e['instructions']:,.0f} ({e['against_rlbox_only_percent']:+.3f}%, repeats differ by "
                           f"{e['largest_difference_between_repeats']:,})" for n, e in ins.items()))
    if workload == "file_sync_194mb":
        perf.append(("app", "rsync/popt", label, "Runtime (s)", med["native"] / 1e9, med["rlbox_only"] / 1e9,
                     med["extended_sp3"] / 1e9, d, ins["interspec"]["against_rlbox_only_percent"], 3))

total, reps, medians = sliced(CAMP / "r3/yaml-sliced/run")
first = next(csv.DictReader((CAMP / "r3/yaml-sliced/run/samples.csv").open()))
rounds = max(int(r["round"]) for r in csv.DictReader((CAMP / "r3/yaml-sliced/run/samples.csv").open()))
parses = rounds * 12  # 12 parses per slice (the arguments of the step in after.sh)
d = triple([total[(i, "interspec")] / total[(i, "rlbox-only")] for i in reps])
sandbox = triple([total[(i, "rlbox-only")] / total[(i, "native")] for i in reps])
nocheck = triple([total[(i, "tracked-no-check")] / total[(i, "rlbox-only")] for i in reps])
yaml_ins = json.loads((CAMP / "r3/yaml/run/summary.json").read_text())["workloads"]["yaml_parse_1mb"]
perf.append(("app", "yaml/libyaml", "1\\,MiB document", "Time per parse (ms)", medians["native"] / parses / 1e6,
             medians["rlbox-only"] / parses / 1e6, medians["interspec"] / parses / 1e6, d,
             yaml_ins["interspec"]["against_rlbox_only_percent"], 2))
notes.append(f"- yaml sliced ({rounds} slices of 12 parses): RLBox-only against native {sandbox[0]:+.1f}% "
             f"({sandbox[1]:+.1f} to {sandbox[2]:+.1f}); registry without checks against RLBox-only "
             f"{nocheck[0]:+.1f}% ({nocheck[1]:+.1f} to {nocheck[2]:+.1f}); instructions per parse: " +
             ", ".join(f"{n} {e['instructions']:,.0f} ({e['against_rlbox_only_percent']:+.3f}%, repeats differ by "
                       f"{e['largest_difference_between_repeats']:,})" for n, e in yaml_ins.items()))

# --- library workloads -----------------------------------------------------
for boundary, name, workload, metric, unit, digits in (
        ("ffmpeg_libvpx", "ffmpeg/libvpx", "VP8 encode and decode", "Time per frame (ms)", 1e6, 2),
        ("magick_libpng", "magick/libpng", "PNG decode and encode", "Time per image (\\textmu{}s)", 1e3, 1),
        ("memcached_hash", "memcached/hash", "Hash function", "Time per call (ns)", 1, 1),
        ("memcached_assoc", "memcached/hash", "Hash table", "Time per operation (ns)", 1, 0),
        ("nginx_openssl", "nginx/openssl", "TLS~1.3 request and response", "Time per exchange (\\textmu{}s)", 1e3, 1),
        ("ucl_libucl", "ucl/libucl", "Parse, look up, emit", "Time per iteration (\\textmu{}s)", 1e3, 2),
        ("zip_libzip", "zip/libzip", "Metadata queries", "Time per query (ns)", 1, 0)):
    port_row("lib", CAMP / f"p7/{boundary}/run", CAMP / f"instr/{boundary}/run", boundary, name, workload,
             metric, unit, digits)
port_row("lib", CAMP / "p7/zip_libzip_listing/run", CAMP / "instr/zip_libzip_listing/run", "zip_libzip_listing", "zip/libzip",
         "Archive listing, 1,000 entries", "Time per listing (\\textmu{}s)", 1e3, 1)


def geomean(values):
    return 100 * (math.exp(sum(math.log(1 + v / 100) for v in values) / len(values)) - 1)


lines, summary = [], []
for group, title in (("app", "Complete application"), ("lib", "Library workload")):
    mine = [p for p in perf if p[0] == group]
    lines.append(f"\\multicolumn{{9}}{{@{{}}l}}{{\\textit{{{title}}}}} \\\\")
    for _, name, workload, metric, native, rlbox, interspec, d, ins, digits in mine:
        cell = "--" if ins is None else tex(ins)
        lines.append(f"{name} & {workload} & {metric}\n  & {native:.{digits}f} & {rlbox:.{digits}f} & "
                     f"{interspec:.{digits}f} & {tex(d[0])} & [{tex(d[1])}, {tex(d[2])}] & {cell} \\\\")
    mean = geomean([p[7][0] for p in mine])
    lines.append(f"\\multicolumn{{6}}{{@{{}}l}}{{Geometric mean}} & {tex(mean)} & & \\\\")
    lines.append("\\midrule" if group == "app" else "\\bottomrule")
    zero = [p for p in mine if p[7][1] <= 0 <= p[7][2]]
    faster = [p for p in mine if p[7][2] < 0]
    slower = [p for p in mine if p[7][1] > 0]
    summary += [f"## {title}", "",
                f"- measurements: {len(mine)}; range includes zero: {len(zero)} "
                f"(medians {min(p[7][0] for p in zero):+.1f} to {max(p[7][0] for p in zero):+.1f}); "
                f"whole range below zero: {len(faster)} ({', '.join(p[1] + ' ' + p[2] for p in faster)}); "
                f"whole range above zero: {len(slower)} ({', '.join(p[1] + ' ' + p[2] for p in slower)})",
                f"- geometric mean of the {len(mine)} medians: {mean:+.2f}%",
                "- instruction differences where counted: " +
                ", ".join(f"{p[1]} {p[2]} {p[8]:+.2f}%" for p in mine if p[8] is not None), ""]
    for p in mine:
        summary.append(f"- {p[1]}, {p[2]}: native {p[4]:.3f}, RLBox-only {p[5]:.3f}, InterSpec {p[6]:.3f} "
                       f"[{p[3]}]; {p[7][0]:+.1f}% ({p[7][1]:+.1f} to {p[7][2]:+.1f})")
    summary.append("")
summary.append(f"- geometric mean of all {len(perf)} medians: {geomean([p[7][0] for p in perf]):+.2f}%")
(out / "perf_rows.tex").write_text("\n".join(lines) + "\n")

# --- per-policy table ------------------------------------------------------
COLS = ["interspec-sp1", "interspec-sp2", "interspec-sp3", "interspec-all-on"]
policy, policy_notes = [], []


def policy_rows(directory, labels):
    run = json.loads((directory / "run.json").read_text())
    rows = list(csv.DictReader((directory / "samples.csv").open()))
    if "workloads" in run:
        higher = run["unit"].endswith("_per_s")
        groups = [(w, [r for r in rows if r["workload"] == w], "value") for w in run["workloads"]]
    else:
        higher, groups = False, [(run["harness_entry"], rows, "elapsed_ns")]
    for name, subset, field in groups:
        slices = collections.defaultdict(list)
        for r in subset:
            slices[(int(r["repetition"]), r["configuration"])].append(float(r[field]))
        by = {k: (st.mean(v) if higher else sum(v)) for k, v in slices.items()}
        reps = sorted({k[0] for k in by})

        def cost(config, base):
            return triple([(by[(i, base)] / by[(i, config)]) if higher else (by[(i, config)] / by[(i, base)])
                           for i in reps])
        cells = [cost(c, "interspec-all-off") if (reps[0], c) in by else None for c in COLS]
        on, off = cost("interspec-all-on", "rlbox-only"), cost("interspec-all-off", "rlbox-only")
        policy.append((labels[name], cells))
        policy_notes.append(
            f"- {labels[name]}: " + "; ".join(
                f"{c.split('-', 1)[1]} " + ("no such policy" if t is None else f"{t[0]:+.1f}% ({t[1]:+.1f} to {t[2]:+.1f})")
                for c, t in zip(COLS, cells)) +
            f"; all on against RLBox-only {on[0]:+.1f}% ({on[1]:+.1f} to {on[2]:+.1f}); "
            f"all off against RLBox-only {off[0]:+.1f}% ({off[1]:+.1f} to {off[2]:+.1f})")


policy_rows(CAMP / "p6-apps/memcached/run", {"watch_moderate": "memcached/bipbuffer"})
policy_rows(CAMP / "p6-apps/nginx/run", {"regex_location_4_threads": "nginx/libpcre"})
policy_rows(CAMP / "p6-apps/rsync/run", {"option_parse": "rsync/popt, option parsing",
                                       "file_sync_194mb": "rsync/popt, file sync"})
yaml_run = json.loads((CAMP / "p6-apps/yaml/run/run.json").read_text())
policy_rows(CAMP / "p6-apps/yaml/run", {w: "yaml/libyaml" for w in yaml_run.get("workloads", [yaml_run.get("harness_entry")])})
for boundary, label in (("ffmpeg_libvpx", "ffmpeg/libvpx"), ("magick_libpng", "magick/libpng"),
                        ("memcached_hash", "memcached/hash, function"), ("memcached_assoc", "memcached/hash, table"),
                        ("nginx_openssl", "nginx/openssl"), ("ucl_libucl", "ucl/libucl"),
                        ("zip_libzip", "zip/libzip, queries"), ("zip_libzip_listing", "zip/libzip, listing")):
    directory = CAMP / f"p6-ports/{boundary}/run"
    entry = json.loads((directory / "run.json").read_text())["harness_entry"]
    policy_rows(directory, {entry: label})

lines = []
for label, cells in policy:
    shown = []
    for t in cells:
        if t is None:
            shown.append("--")
        elif t[1] > 0 or t[2] < 0:
            shown.append(f"\\textbf{{{tex(t[0])}}}")
        else:
            shown.append(tex(t[0]))
    lines.append(f"{label} & " + " & ".join(shown) + " \\\\")
(out / "policy_rows.tex").write_text("\n".join(lines) + "\n")
measurable = [label for label, cells in policy if cells[3][1] > 0 or cells[3][2] < 0]
summary += ["", "## Per-policy table", "",
            f"- rows: {len(policy)}; rows whose combined cost has its whole range on one side of zero: "
            f"{len(measurable)} ({', '.join(measurable)})", ""] + policy_notes
(out / "NUMBERS.md").write_text("\n".join(["# Numbers of the performance subsection", ""] + summary +
                                          ["", "## Details", ""] + notes) + "\n")
print((out / "NUMBERS.md").read_text())
