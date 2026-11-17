#!/usr/bin/env python3
"""Inferred, checked and exercised SP3 fields per boundary (tracker item R6).

For every pointer field that needs SP3 the table answers three questions, each
from a different source:

  inferred   Does the analysis list the field? Source: the artifact's
             data/raw/policy_reports/<boundary>/sp3_cases.csv.
  checked    Does the wrapper check it against the registry? Source: the
             wrapper's source file; the status file names the file and a text
             that performs the check, and this tool fails if the text is not
             there. It prints the line.
  exercised  Does the measured workload reach it? Source: the raw outputs of
             the measurements. For the single-process workloads this is the
             number of calls of the library function in the callgrind profile
             of the InterSpec build (two iteration counts, difference
             quotient; for rsync the calls of a whole run). For the two
             servers it is the number of events in the registry trace of the
             deployment test, which sends the request types of the timed
             workload.

The join between a case of the artifact and a field of a port is the one of
tools/render_sp3_metadata_table.py (evaluation/coverage/sp3_metadata_sources.json).
"""

import argparse
import collections
import csv
import json
import re
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_sp3_metadata_table import NAMES  # noqa: E402


def profile_calls(handle):
    """Calls per callee name in one callgrind profile."""
    names, total, pending = {}, collections.Counter(), None
    for raw in handle:
        line = raw.decode(errors="replace")
        match = re.match(r"c?fn=\((\d+)\)(?: (.*))?", line)
        if match:
            if match.group(2):
                names[match.group(1)] = match.group(2).strip()
            pending = match.group(1) if line.startswith("cfn=") else None
        elif line.startswith("calls=") and pending:
            total[pending] += int(line[6:].split()[0])
            pending = None
    result = collections.Counter()
    for key, count in total.items():
        result[names.get(key, key)] += count
    return result


class Source:
    """The raw output of one measurement, opened once."""

    def __init__(self, root, spec):
        self.spec, self.kind = spec, spec["kind"]
        archive = tarfile.open(root / spec["archive"])
        if self.kind == "profiles":      # two iteration counts
            self.low = self.sum(archive, spec["low_members"])
            self.high = self.sum(archive, spec["high_members"])
            self.per = spec["high"] - spec["low"]
        elif self.kind == "run-profiles":  # one whole run, all its processes
            self.high, self.low, self.per = self.sum(archive, spec["members"]), collections.Counter(), 1
        else:                              # registry trace
            text = archive.extractfile(spec["member"]).read().decode(errors="replace")
            self.events = collections.Counter()
            for line in text.splitlines():
                if line.startswith("INTERSPEC "):
                    fields = dict(t.split("=", 1) for t in line.split()[1:] if "=" in t)
                    self.events[(fields.get("event"), fields.get("site"))] += 1
                    self.events[(fields.get("event"), None)] += 1

    @staticmethod
    def sum(archive, pattern):
        total, found = collections.Counter(), 0
        for member in archive.getmembers():
            if re.fullmatch(pattern, member.name):
                total.update(profile_calls(archive.extractfile(member)))
                found += 1
        if not found:
            sys.exit(f"no member matches {pattern}")
        return total

    def count(self, exercise):
        """(number, text) for one field."""
        unit = self.spec["unit"]
        if self.kind == "trace":
            key = (exercise["event"], str(exercise["site"]) if "site" in exercise else None)
            number = self.events[key]
            what = exercise["event"] + (f" at site {exercise['site']}" if "site" in exercise else "")
            return number, f"{number:,} `{what}` events in {unit}"
        pattern = re.compile(r"w2c_\w*?_" + exercise["symbol"] + r"(_0)?(\.\w+)*")
        names = [n for n in self.high if pattern.fullmatch(n)]
        number = sum(self.high[n] - self.low[n] for n in names) / self.per
        if not names or not number:
            return 0, f"`{exercise['symbol']}` is not called"
        shown = f"{number:,.2f}".rstrip("0").rstrip(".") if number >= 0.01 else f"{number:.2g}"
        noun = "call" if shown == "1" else "calls"
        return number, f"{shown} {noun} of `{exercise['symbol']}` per {unit}"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--artifact-reports", required=True, type=Path)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--status", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path, help="this repository")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    records = json.loads(args.records.read_text())
    status = json.loads(args.status.read_text())
    without = records["boundaries_without_fields"]
    sources = {name: Source(args.root, spec) for name, spec in status["sources"].items()}

    inferred, unjoined = set(), {}
    for benchmark in NAMES:
        path = args.artifact_reports / benchmark / "sp3_cases.csv"
        if benchmark in without:
            unjoined[benchmark] = "not joined"
            continue
        if not path.exists():  # the column cannot be filled for this boundary
            unjoined[benchmark] = "no case file"
            continue
        for row in csv.DictReader(path.open()):
            inferred.add((benchmark, "|".join([row["function"], row["binding_kind"],
                                               row["binding_id"], row["slot_path"]])))

    rows, errors = [], []
    for record in records["fields"]:
        benchmark, key = record["benchmark"], record["key"]
        entry = status["fields"].get(f"{benchmark}|{key}")
        if entry is None:
            errors.append(f"no status entry for {benchmark}|{key}")
            continue
        is_inferred = (benchmark, key) in inferred
        if record.get("origin") != "port" and not is_inferred:
            errors.append(f"record without a case in the artifact: {benchmark}|{key}")
        site = entry.get("check_site")
        if (record["checked_by_port"] == "yes") != (site is not None):
            errors.append(f"check_site and checked_by_port disagree: {benchmark}|{key}")
            continue
        checked = ""
        if site:
            lines = (args.root / site["file"]).read_text().splitlines()
            start = 0
            if "after" in site:  # the first line with the text after a line that occurs once
                anchors = [i for i, line in enumerate(lines) if site["after"] in line]
                if len(anchors) != 1:
                    errors.append(f"{site['file']}: {len(anchors)} lines contain {site['after']!r}")
                    continue
                start = anchors[0]
            hits = [i + 1 for i, line in enumerate(lines) if i >= start and site["text"] in line]
            if not hits or ("after" not in site and len(hits) != 1):
                errors.append(f"{site['file']}: {len(hits)} lines contain {site['text']!r}")
                continue
            checked = f"`{site['file']}:{hits[0]}`"
        exercise, number, exercised = entry.get("exercise"), None, entry.get("not_exercised", "")
        if exercise:
            number, exercised = sources[exercise["source"]].count(exercise)
        rows.append({"benchmark": benchmark, "field": key, "inferred": is_inferred,
                     "checked": checked, "checked_by_port": record["checked_by_port"],
                     "number": number, "exercised": exercised,
                     "note": entry.get("note", "")})
    if errors:
        sys.exit("\n".join(errors))

    lines = ["# SP3 fields: inferred, checked, exercised", "",
             "Generated by `tools/render_sp3_field_status.py` (see its header for the three",
             "sources). \"Inferred\" counts the cases in the artifact's `sp3_cases.csv`;",
             "\"checked\" the fields with a registry check in the wrapper; \"exercised\" the",
             "checked fields that the measured workload reaches at least once.", "",
             "## Counts", "",
             "| Boundary | Inferred by the analysis | of these, checked by the wrapper | "
             "Checked by the wrapper, all | of these, exercised by the measured workload | "
             "Checked without a case of the analysis |",
             "|---|---:|---:|---:|---:|---:|"]
    totals = collections.Counter()
    for benchmark, name in NAMES.items():
        mine = [r for r in rows if r["benchmark"] == benchmark]
        counts = {"inferred": sum(r["inferred"] for r in mine),
                  "inferred_checked": sum(r["inferred"] and bool(r["checked"]) for r in mine),
                  "checked": sum(bool(r["checked"]) for r in mine),
                  "exercised": sum(bool(r["checked"]) and bool(r["number"]) for r in mine),
                  "port_only": sum(bool(r["checked"]) and not r["inferred"] for r in mine)}
        shown = dict(counts)
        if benchmark in unjoined:
            shown["inferred"] = shown["inferred_checked"] = shown["port_only"] = unjoined[benchmark]
        else:
            totals.update({k: counts[k] for k in ("inferred", "inferred_checked", "port_only")})
        totals.update({k: counts[k] for k in ("checked", "exercised")})
        lines.append(f"| {name} | {shown['inferred']} | {shown['inferred_checked']} | "
                     f"{shown['checked']} | {shown['exercised']} | {shown['port_only']} |")
    lines.append(f"| Total | {totals['inferred']} | {totals['inferred_checked']} | "
                 f"{totals['checked']} | {totals['exercised']} | {totals['port_only']} |")
    lines += ["", "The first, second and last column are totals over the boundaries with a joined",
              "case file (" + str(len(NAMES) - len(unjoined)) + " of " + str(len(NAMES)) + ").", ""]
    for benchmark, why in unjoined.items():
        reason = without.get(benchmark) or ("The artifact has no `sp3_cases.csv` for this boundary, so the tool "
                                            "cannot say which of the port's fields the analysis infers.")
        lines += [f"{NAMES[benchmark]} ({why}): {reason}", ""]
    for benchmark, name in NAMES.items():
        mine = [r for r in rows if r["benchmark"] == benchmark]
        if not mine:
            continue
        lines += [f"## {name}", "",
                  "| Field | Inferred | Checked by the wrapper | In the measured workload | Note |",
                  "|---|---|---|---|---|"]
        for r in mine:
            reason = "" if r["checked_by_port"] == "no" else f" ({r['checked_by_port']})"
            checked = r["checked"] or "no" + reason
            shown_inferred = unjoined.get(benchmark) or ("yes" if r["inferred"] else "no")
            lines.append(f"| `{r['field'].replace('|', ' / ')}` | {shown_inferred} | "
                         f"{checked} | {r['exercised']} | {r['note']} |")
        lines.append("")
    lines += ["## Sources of the last column", ""]
    for name, spec in status["sources"].items():
        lines.append(f"- {name}: {spec['what']} (`{spec['archive']}`)")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n")
    print(f"{len(rows)} fields; checked {totals['checked']}, of these exercised {totals['exercised']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
