#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path


LIMITATION_TEXT = {
    "no_general_cfi": "Allocation-site provenance is not general control-flow integrity.",
    "u_object_contents_untrusted": "U-owned object contents remain untrusted even when allocation metadata is trusted.",
    "no_physical_address_reuse": "The typed arena does not physically reuse released numerical addresses.",
    "no_same_type_object_identity": "The runtime does not bind a use to one particular simultaneously live allocation among multiple allocations of the same trusted type.",
    "abi_marshalling_application_specific": "Arbitrary library ABI marshalling remains application-specific.",
    "p7c_use_adapters_not_real_application_inference": "The memcached, PCRE, and libyaml P7c trusted-use policies are representative analysis adapters rather than automatic inference from those applications' original T-side source.",
}


def load_json(path):
    return json.loads(Path(path).read_text())


def read_csv(path):
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, fieldnames, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def resolve(root, value):
    path = Path(value)
    return path if path.is_absolute() else root / path


def collect_automation(root, p7c_manifest):
    rows = []
    totals = {
        "source_allocation_sites": 0,
        "precise_source_allocation_sites": 0,
        "integration_helper_sites": 0,
        "adversarial_helper_sites": 0,
        "trusted_use_policies": 0,
        "real_application_use_policies": 0,
        "analysis_adapter_use_policies": 0,
    }

    for entry in p7c_manifest["boundaries"]:
        policy = load_json(resolve(root, entry["policy"]))
        boundary = load_json(resolve(root, entry["boundary_policy"]))
        allocations = policy.get("allocations", [])
        uses = policy.get("uses", [])
        helpers = boundary.get("helper_sites", [])
        integration_helpers = [h for h in helpers if h.get("role", "integration") == "integration"]
        adversarial_helpers = [h for h in helpers if h.get("role", "integration") == "adversarial"]
        unknown_roles = sorted({h.get("role", "integration") for h in helpers} - {"integration", "adversarial"})
        if unknown_roles:
            raise ValueError(f"{entry['name']}: unknown helper roles: {unknown_roles}")

        precise = [a for a in allocations if "site" in a]
        dynamic_uses = [u for u in uses if u.get("dynamic_bytes")]
        use_evidence = entry.get("trusted_use_evidence")
        if use_evidence not in {"real_application_source", "analysis_adapter"}:
            raise ValueError(f"{entry['name']}: missing/invalid trusted_use_evidence")

        production_sites = len(allocations) + len(integration_helpers)
        source_fraction = (
            len(allocations) / production_sites if production_sites else 0.0
        )
        row = {
            "boundary": entry["name"],
            "source_revision": entry["source_revision"],
            "pointer_shapes": ";".join(entry.get("pointer_shapes", [])),
            "source_allocation_sites": len(allocations),
            "precise_source_allocation_sites": len(precise),
            "integration_helper_sites": len(integration_helpers),
            "adversarial_helper_sites": len(adversarial_helpers),
            "production_allocation_sites": production_sites,
            "source_allocation_fraction": f"{source_fraction:.6f}",
            "trusted_use_policies": len(uses),
            "dynamic_use_policies": len(dynamic_uses),
            "trusted_use_evidence": use_evidence,
            "trusted_use_source": entry.get("trusted_use_source", ""),
            "allocation_evidence": entry.get("allocation_evidence", ""),
        }
        rows.append(row)

        totals["source_allocation_sites"] += len(allocations)
        totals["precise_source_allocation_sites"] += len(precise)
        totals["integration_helper_sites"] += len(integration_helpers)
        totals["adversarial_helper_sites"] += len(adversarial_helpers)
        totals["trusted_use_policies"] += len(uses)
        if use_evidence == "real_application_source":
            totals["real_application_use_policies"] += len(uses)
        else:
            totals["analysis_adapter_use_policies"] += len(uses)

    production = totals["source_allocation_sites"] + totals["integration_helper_sites"]
    totals["production_allocation_sites"] = production
    totals["source_allocation_fraction"] = (
        totals["source_allocation_sites"] / production if production else 0.0
    )
    return rows, totals


def collect_runtime_security(rows, required_cases):
    by_case = {row["case"]: row for row in rows}
    result_rows = []
    for case in required_cases:
        if case not in by_case:
            raise ValueError(f"missing required runtime security case: {case}")
        row = by_case[case]
        if row.get("result") != "pass":
            raise ValueError(f"runtime security case failed: {case}")
        result_rows.append({
            "case": case,
            "expected": row.get("expected", ""),
            "actual": row.get("actual", ""),
            "result": row.get("result", ""),
        })
    return result_rows


def collect_boundary_security(p7c_manifest, requirements, evidence_rows, require_evidence):
    declared = {entry["name"]: set(entry.get("adversarial", [])) for entry in p7c_manifest["boundaries"]}
    evidence = {}
    for row in evidence_rows:
        key = (row.get("boundary", ""), row.get("case", ""))
        evidence[key] = row.get("result", "")

    rows = []
    for boundary, cases in requirements.items():
        if boundary not in declared:
            raise ValueError(f"boundary missing from P7c manifest: {boundary}")
        for case in cases:
            if case not in declared[boundary]:
                raise ValueError(f"{boundary}: required attack not declared: {case}")
            actual = evidence.get((boundary, case))
            if require_evidence and actual != "pass":
                raise ValueError(f"{boundary}: missing passing RLBox evidence for {case}")
            rows.append({
                "boundary": boundary,
                "case": case,
                "expected": "reject",
                "result": actual if actual is not None else "declared",
                "evidence": "rlbox_nacl_regression" if actual is not None else "manifest_declaration",
            })
    return rows


def parse_runtime(rows):
    result = {}
    for row in rows:
        key = (row["metric"], int(row["population"]), int(row["threads"]))
        if key in result:
            raise ValueError(f"duplicate runtime metric row: {key}")
        operations = int(row["operations"])
        total_ns = int(row["total_ns"])
        if operations <= 0 or total_ns <= 0:
            raise ValueError(f"invalid runtime measurement: {key}")
        result[key] = {
            "operations": operations,
            "total_ns": total_ns,
            "ns_per_op": total_ns / operations,
        }
    return result


def collect_runtime_overhead(runtime_rows, pairs, populations):
    metrics = parse_runtime(runtime_rows)
    rows = []
    for pair in pairs:
        for population in populations:
            baseline_key = (pair["baseline_metric"], population, 1)
            extended_key = (pair["extended_metric"], population, 1)
            if baseline_key not in metrics:
                raise ValueError(f"missing runtime baseline row: {baseline_key}")
            if extended_key not in metrics:
                raise ValueError(f"missing Extended-SP3 runtime row: {extended_key}")
            baseline = metrics[baseline_key]["ns_per_op"]
            extended = metrics[extended_key]["ns_per_op"]
            if baseline <= 0:
                raise ValueError(f"zero runtime baseline for {pair['name']} at {population}")
            rows.append({
                "comparison": pair["name"],
                "population": population,
                "baseline_metric": pair["baseline_metric"],
                "extended_metric": pair["extended_metric"],
                "baseline_ns_per_op": f"{baseline:.6f}",
                "extended_ns_per_op": f"{extended:.6f}",
                "additional_ns_per_op": f"{extended - baseline:.6f}",
                "extended_over_baseline": f"{extended / baseline:.6f}",
            })
    return rows


def render_markdown(summary, automation_rows, runtime_rows, boundary_rows):
    lines = [
        "# P8 Generated Results",
        "",
        "This file is generated from machine-readable P8 inputs. Do not edit paper numbers here manually.",
        "",
        "## Security",
        "",
        f"Runtime security cases required/passed: **{summary['security']['runtime_cases_passed']} / {summary['security']['runtime_cases_required']}**.",
        f"Boundary attack cases required/covered: **{summary['security']['boundary_cases_covered']} / {summary['security']['boundary_cases_required']}**.",
        "",
        "| Boundary | Attack class | Evidence | Result |",
        "| --- | --- | --- | --- |",
    ]
    for row in boundary_rows:
        lines.append(f"| {row['boundary']} | {row['case']} | {row['evidence']} | {row['result']} |")

    lines += [
        "",
        "## Automation and generalization",
        "",
        "| Boundary | Source allocation sites | Integration helper sites | Adversarial-only helper sites | Trusted uses | Use evidence |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in automation_rows:
        lines.append(
            f"| {row['boundary']} | {row['source_allocation_sites']} | "
            f"{row['integration_helper_sites']} | {row['adversarial_helper_sites']} | "
            f"{row['trusted_use_policies']} | {row['trusted_use_evidence']} |"
        )

    a = summary["automation"]
    lines += [
        "",
        f"Across production allocation policy, **{a['source_allocation_sites']}** sites are source-derived and **{a['integration_helper_sites']}** are explicit integration helpers. Attack-only helper sites (**{a['adversarial_helper_sites']}**) are excluded from that denominator.",
        f"The resulting source-derived allocation-site share is **{100.0 * a['source_allocation_fraction']:.1f}%** under this explicitly defined metric.",
        f"Trusted-use policies: **{a['real_application_use_policies']}** from real application source and **{a['analysis_adapter_use_policies']}** from P7c analysis adapters.",
        "",
        "## Incremental primitive cost",
        "",
        "The baseline below is an original-SP3-style U-domain/range check. The Extended-SP3 measurement adds live-allocation lookup, expected type, and containing-object bounds.",
        "",
        "| Comparison | Live allocations | Baseline ns/op | Extended ns/op | Additional ns/op | Ratio |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in runtime_rows:
        lines.append(
            f"| {row['comparison']} | {row['population']} | "
            f"{float(row['baseline_ns_per_op']):.2f} | {float(row['extended_ns_per_op']):.2f} | "
            f"{float(row['additional_ns_per_op']):.2f} | {float(row['extended_over_baseline']):.2f}× |"
        )

    lines += ["", "## Preserved limitations", ""]
    for item in summary["limitations"]:
        lines.append(f"• {item['text']}")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="evaluation/p8_manifest.json")
    parser.add_argument("--root")
    parser.add_argument("--security", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--boundary-security")
    parser.add_argument("--require-boundary-evidence", action="store_true")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    manifest = load_json(resolve(root, args.manifest))
    p7c_manifest = load_json(resolve(root, manifest["p7c_manifest"]))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    automation_rows, automation_totals = collect_automation(root, p7c_manifest)
    runtime_security = collect_runtime_security(
        read_csv(args.security), manifest["required_runtime_security_cases"])
    boundary_evidence = read_csv(args.boundary_security) if args.boundary_security else []
    boundary_security = collect_boundary_security(
        p7c_manifest,
        manifest["boundary_security_requirements"],
        boundary_evidence,
        args.require_boundary_evidence,
    )
    runtime_overhead = collect_runtime_overhead(
        read_csv(args.runtime),
        manifest["runtime_pairs"],
        manifest["required_runtime_populations"],
    )

    limitations = []
    for key in manifest["required_limitations"]:
        if key not in LIMITATION_TEXT:
            raise ValueError(f"unknown required limitation: {key}")
        limitations.append({"id": key, "text": LIMITATION_TEXT[key]})

    boundary_required = sum(len(v) for v in manifest["boundary_security_requirements"].values())
    boundary_covered = sum(1 for row in boundary_security if row["result"] == "pass")
    summary = {
        "schema_version": 1,
        "security": {
            "runtime_cases_required": len(manifest["required_runtime_security_cases"]),
            "runtime_cases_passed": len(runtime_security),
            "boundary_cases_required": boundary_required,
            "boundary_cases_covered": boundary_covered,
            "boundary_evidence_required": args.require_boundary_evidence,
        },
        "automation": automation_totals,
        "runtime": {
            "paired_measurements": len(runtime_overhead),
            "max_extended_over_baseline": max(
                float(row["extended_over_baseline"]) for row in runtime_overhead
            ),
            "max_additional_ns_per_op": max(
                float(row["additional_ns_per_op"]) for row in runtime_overhead
            ),
        },
        "limitations": limitations,
    }

    write_csv(out / "automation.csv", list(automation_rows[0].keys()), automation_rows)
    write_csv(out / "security-runtime.csv", list(runtime_security[0].keys()), runtime_security)
    write_csv(out / "security-boundaries.csv", list(boundary_security[0].keys()), boundary_security)
    write_csv(out / "runtime-overhead.csv", list(runtime_overhead[0].keys()), runtime_overhead)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out / "summary.md").write_text(
        render_markdown(summary, automation_rows, runtime_overhead, boundary_security)
    )


if __name__ == "__main__":
    main()
