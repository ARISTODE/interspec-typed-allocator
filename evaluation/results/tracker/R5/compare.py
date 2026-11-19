#!/usr/bin/env python3
"""R5: compare two runs of the pointer analysis with different depth limits, and group the
pointers without an inferred domain by the assignments that write them.

usage: compare.py CLASSIFICATION_LOW CLASSIFICATION_HIGH [SLOT_WRITES_CSV]

Field classes follow ../C2/19-unresolved-pointer-fields-by-cause/unresolved_causes.py: a pointer
field needs SP3 when a pointer at or below it is influenced by U and used by T; it is resolved when
every such pointer has an expected domain and is not at the depth limit of the run."""
import collections
import csv
import sys


def load(path):
    slots = {}
    for r in csv.DictReader(open(path)):
        k = (r["function"], r["binding_kind"], r["binding_id"], r["slot_path"])
        s = slots.setdefault(k, dict(u=False, t=False, cut=False, known=False, type=r.get("slot_type", "")))
        s["u"] |= r["u_influenced"] == "1"
        s["t"] |= r["t_uses"] == "1"
        s["cut"] |= r["flow_cut"] == "1"
        s["w"] = s.get("w", False) or r["u_writes"] == "1"
        s["known"] |= r["sp3_target_t"] == "1" or r["sp3_target_u"] == "1" or r["sp3_target_null"] == "1"
    return slots


def classes(slots):
    sp3 = {k: v for k, v in slots.items() if v["u"] and v["t"]}
    by = collections.defaultdict(list)
    for (f, bk, bi, p), v in sp3.items():
        by[(f, bk, bi)].append((p, v))
    out = {}
    for (f, bk, bi, p), v in slots.items():
        below = [x for q, x in by.get((f, bk, bi), []) if p == "" or q == p or q.startswith(p + "/")]
        if not below:
            continue
        unknown, cut = any(not x["known"] for x in below), any(x["cut"] for x in below)
        out[(f, bk, bi, p)] = ("resolved" if not unknown and not cut else "unknown domain and depth limit" if unknown and cut
                               else "unknown domain only" if unknown else "depth limit only")
    return sp3, out


def main():
    low, high = load(sys.argv[1]), load(sys.argv[2])
    sp3_low, class_low = classes(low)
    sp3_high, class_high = classes(high)
    for name, sp3, cls in (("low", sp3_low, class_low), ("high", sp3_high, class_high)):
        count = collections.Counter(cls.values())
        print(f"{name}: fields that need SP3 {len(cls):,}: " + ", ".join(f"{k} {v:,}" for k, v in sorted(count.items()))
              + f"; pointers that need SP3 {len(sp3):,}, at the limit {sum(v['cut'] for v in sp3.values()):,}, "
              f"without a domain {sum(not v['known'] for v in sp3.values()):,}")
    print("\nfields of the low run by their class in the high run:")
    move = collections.Counter((c, class_high.get(k, "does not need SP3 in the high run")) for k, c in class_low.items())
    for (a, b), n in sorted(move.items()):
        print(f"  {a:32s} -> {b:36s} {n:6,}")
    print("\npointers of the low run that are at its limit, in the high run:")
    at = [k for k, v in sp3_low.items() if v["cut"]]
    fate = collections.Counter()
    for k in at:
        v = sp3_high.get(k)
        fate["not a pointer that needs SP3" if v is None else ("has a domain" if v["known"] else "no domain")] += 1
    print("  " + ", ".join(f"{k} {v:,}" for k, v in sorted(fate.items())))
    new = [k for k in sp3_high if k not in low]
    print(f"pointers that need SP3 and exist only in the high run: {len(new):,}, "
          f"{sum(sp3_high[k]['cut'] for k in new):,} at its limit, {sum(not sp3_high[k]['known'] for k in new):,} without a domain")
    if len(sys.argv) < 4:
        return
    writes = collections.defaultdict(list)
    for r in csv.DictReader(open(sys.argv[3])):
        writes[(r["function"], r["binding_id"], r["slot_path"])].append(r)
    unknown = [k for k, v in sp3_low.items() if not v["known"]]
    group = collections.Counter(); kinds = collections.Counter(); callees = collections.Counter()
    for (f, bk, bi, p) in unknown:
        rows = writes.get((f, bi, p), [])
        if not rows:
            group["no assignment found within three calls"] += 1
            continue
        k = sorted({r["rhs_class"] for r in rows})
        classified = any(r["rule_t"] == "1" or r["rule_u"] == "1" or r["rule_null"] == "1" for r in rows)
        group["assignments found, at least one classified by a rule" if classified else "assignments found, none classified"] += 1
        kinds[" + ".join(k)] += 1
        for c in {r["rhs_callee"] for r in rows if r["rhs_callee"]}:
            callees[c] += 1
    print(f"\npointers without a domain in the low run: {len(unknown):,}")
    for k, v in group.most_common():
        print(f"  {k}: {v:,}")
    print("kinds of right-hand side, per pointer with assignments:")
    for k, v in kinds.most_common(12):
        print(f"  {v:5,}  {k}")
    print("functions whose result is assigned, per pointer:")
    for k, v in callees.most_common(12):
        print(f"  {v:5,}  {k}")
    written = collections.defaultdict(list)
    for (f, bk, bi, p), v in low.items():
        if v["w"]:
            written[(f, bk, bi)].append(p)
    where = collections.Counter(); ancestor = collections.Counter()
    for (f, bk, bi, p) in unknown:
        if low[(f, bk, bi, p)]["w"]:
            where["written by U itself"] += 1
            continue
        above = [w for w in written[(f, bk, bi)] if p.startswith(w + "/")]
        if above:
            where["not written by U, behind a pointer that U writes"] += 1
            ancestor[(f, max(above, key=len))] += 1
        else:
            where["not written by U, no written pointer above it"] += 1
    print("why they count as influenced by U:")
    for k, v in where.most_common():
        print(f"  {k}: {v:,}")
    print(f"written pointers that they lie behind: {len(ancestor)}; the largest:")
    for (f, w), v in ancestor.most_common(14):
        print(f"  {v:5,}  {f}: {w}")
    types = collections.Counter(sp3_low[k]["type"] for k in unknown)
    print("types:", ", ".join(f"{k} {v}" for k, v in types.most_common(6)))


if __name__ == "__main__":
    main()
