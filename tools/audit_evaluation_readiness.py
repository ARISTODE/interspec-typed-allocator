#!/usr/bin/env python3
"""Verify retained evidence and render application/microbenchmark readiness.

Run summarize_selected_evaluation.py first to revalidate application pairings
and correctness. This audit additionally checks all retained artifact hashes,
the repeated runtime matrix, and source-attributed P8 CI log extracts.
"""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation/results"
MEMCACHED = RESULTS / "memcached-overhead/hosted-37593628863"
P8 = RESULTS / "microbenchmarks/hosted-37840970704"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text())


def read_csv(path):
    return list(csv.DictReader(path.open(newline="")))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_runtime_keys():
    keys = {(metric, population, 1)
            for population in (2, 16, 256, 4096, 16384)
            for metric in ("shared_lock", "metadata_lookup", "check_live",
                           "check_interior", "check_wrong_type", "remaining_bytes")}
    keys |= {(metric, 2, 1) for metric in ("type_compare", "bounds_check")}
    keys |= {(metric, 16384, 1) for metric in ("allocate", "allocate_from_site", "release")}
    keys |= {("check_concurrent", 4096, threads) for threads in (1, 2, 4, 8)}
    return keys


def validate_runtime(raw, repetitions, iterations):
    groups = {}
    for row in raw:
        key = (row["metric"], int(row["population"]), int(row["threads"]))
        repetition = int(row.get("repetition", 0))
        group = groups.setdefault(key, {})
        require(repetition not in group, f"duplicate runtime sample: {key}, {repetition}")
        operations, total = int(row["operations"]), int(row["total_ns"])
        expected_ops = (key[1] if key[0] in ("allocate", "allocate_from_site", "release")
                        else (iterations // 4 + 1) * key[2] if key[0] == "check_concurrent"
                        else iterations)
        value = float(row["ns_per_op"])
        require(operations == expected_ops and total > 0 and math.isfinite(value) and value > 0,
                f"invalid runtime timing: {key}")
        require(math.isclose(value, total / operations, abs_tol=0.00501),
                f"ns/op disagrees with elapsed time: {key}")
        group[repetition] = value
    require(set(groups) == expected_runtime_keys(), "incomplete runtime configuration matrix")
    summaries = []
    for (metric, population, threads), group in sorted(groups.items()):
        require(set(group) == set(range(repetitions)), f"missing runtime repetition: {metric}")
        values = list(group.values())
        summaries.append(dict(metric=metric, population=population, threads=threads, n=len(values),
                              ns_per_op_median=statistics.median(values),
                              ns_per_op_min=min(values), ns_per_op_max=max(values)))
    return summaries


def csv_from_log(path, header, prefixes):
    messages = [line.split("Z ", 1)[1] for line in path.read_text().splitlines() if "Z " in line]
    headers = [line for line in messages if line.startswith(header)]
    require(len(headers) == 1, f"missing or duplicate CSV header: {path}")
    rows = [line for line in messages if line.startswith(prefixes)]
    return headers[0] + "\n" + "\n".join(rows) + "\n"


def main():
    sources = []
    # Verify the original hosted artifacts and their retained data, including
    # raw runtime samples just extracted from the existing memcached archive.
    artifacts = []
    for directory in (MEMCACHED, RESULTS / "yaml-libyaml/hosted-37593628736",
                      RESULTS / "nginx-pcre/hosted-37835791042"):
        provenance = load(directory / "provenance.json")
        archive = directory / "artifact.zip"
        require(digest(archive) == provenance["artifact_sha256"], f"artifact checksum mismatch: {archive}")
        with zipfile.ZipFile(archive) as bundle:
            require(bundle.testzip() is None, f"invalid ZIP: {archive}")
            for path in directory.rglob("*"):
                if not path.is_file() or path == archive:
                    continue
                relative = path.relative_to(directory).as_posix()
                matches = [name for name in bundle.namelist()
                           if name == relative or name.endswith("/" + relative)]
                if len(matches) == 1:
                    require(bundle.read(matches[0]) == path.read_bytes(), f"archive extract mismatch: {path}")
        artifacts.append(dict(path=str(archive.relative_to(ROOT)), sha256=digest(archive),
                              workflow_run_id=provenance["workflow_run_id"]))

    app_sources = load(RESULTS / "selected/source-sha256.json")
    for name, sha in app_sources.items():
        require(digest(ROOT / name) == sha, f"application source checksum mismatch: {name}")
        sources.append(ROOT / name)
    applications = load(RESULTS / "selected/summary.json")
    require(len(applications) == 12, "missing selected workload")
    app_samples = sum(len(read_csv(ROOT / name)) for name in app_sources)

    micro = MEMCACHED / "runtime-microbench"
    raw = read_csv(micro / "raw.csv")
    env = load(micro / "environment.json")
    summary = validate_runtime(raw, env["repetitions"], env["iterations"])
    require(summary == load(micro / "summary.json"), "runtime summary differs from raw samples")
    sources += [micro / name for name in ("raw.csv", "summary.json", "environment.json")]

    checks = load(MEMCACHED / "check-frequency/check-frequency.json")
    require({row["name"] for row in checks} == {row["workload"] for row in applications
                                              if row["benchmark"] == "memcached/bipbuffer"},
            "missing check-frequency scenario")
    for row in checks:
        require(row["operations"] > 0 and row["runtime_checks"] == sum(row["check_operations"].values()),
                "invalid check count")
        require(math.isclose(row["checks_per_operation"], row["runtime_checks"] / row["operations"]),
                "invalid check frequency")
    uncovered = [row["name"] for row in checks if row["runtime_checks"] == 0]
    sources.append(MEMCACHED / "check-frequency/check-frequency.json")

    boundary_csv = csv_from_log(P8 / "boundary-job-excerpt.log", "boundary,repetitions,",
                                ("memcached_bipbuffer,", "nginx_libpcre,", "rsync_popt,", "yaml_libyaml,"))
    boundaries = list(csv.DictReader(io.StringIO(boundary_csv)))
    require(len(boundaries) == 4 and {row["boundary"] for row in boundaries} ==
            {"memcached_bipbuffer", "nginx_libpcre", "rsync_popt", "yaml_libyaml"},
            "incomplete P8 boundary summary")
    require(all(int(row["repetitions"]) == 7 for row in boundaries), "unexpected P8 repetitions")
    require(all(math.isfinite(float(row[key])) and float(row[key]) > 0
                for row in boundaries for key in ("baseline_median_ns", "extended_median_ns")),
            "invalid P8 boundary timing")
    (P8 / "boundary-performance-summary.csv").write_text(boundary_csv)
    runtime_csv = csv_from_log(P8 / "runtime-job-excerpt.log", "metric,population,",
                               tuple(metric + "," for metric, _, _ in expected_runtime_keys()))
    latest_runtime = list(csv.DictReader(io.StringIO(runtime_csv)))
    validate_runtime(latest_runtime, 1, 100000)
    (P8 / "runtime.csv").write_text(runtime_csv)
    sources += [P8 / name for name in ("boundary-job-excerpt.log", "runtime-job-excerpt.log", "provenance.json")]

    gaps = [
        dict(id="memcached_tracking_matrix", status="missing", detail="Tracking-only samples are absent from the selected six-scenario matrix; the separate two-workload pilot does not fill these cells."),
        dict(id="write_heavy_frequency", status="coverage_gap", detail="The 1,000-operation write-heavy diagnostic profile records zero successful checks; no direct check-cost estimate is valid."),
        dict(id="wasm2c_boundary_decomposition", status="not_collected", detail="Empty native versus RLBox call, wrapper mutex, pointer confinement, both copy directions at 64/256/1024/4096 bytes, and complete request+push/offer/peek_all/poll operation costs are outstanding."),
        dict(id="boundary_frequency", status="not_collected", detail="RLBox invocations and T-to-U/U-to-T bytes per client operation are not recorded; existing counts cover SP3 checks only."),
        dict(id="controlled_hardware", status="not_run", detail="All application and microbenchmark publication measurements must use the documented controlled host protocol; memcached needs 30-second intervals, 5-second warmups, 15 pairs and disjoint CPU affinity."),
    ]
    readiness = dict(audit_date="2026-10-09", selected_applications=4, application_workloads=len(applications),
                     application_samples=app_samples, runtime_configurations=len(summary),
                     runtime_samples=len(raw), runtime_repetitions=env["repetitions"],
                     runtime_iterations=env["iterations"], p8_boundary_summaries=len(boundaries),
                     p8_boundary_backend="NaCl", p8_boundary_raw_locally_verified=False,
                     latest_single_pass_runtime_samples=len(latest_runtime),
                     check_frequency_scenarios=len(checks), check_frequency_uncovered=uncovered,
                     all_application_reference_results_present=True, all_planned_results_ready=False,
                     publication_ready=False, artifacts=artifacts, gaps=gaps)
    destination = RESULTS / "selected"
    (destination / "readiness.json").write_text(json.dumps(readiness, indent=2) + "\n")
    (destination / "microbenchmark-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (destination / "microbenchmark-summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary)
    (destination / "audit-source-sha256.json").write_text(json.dumps(
        {str(path.relative_to(ROOT)): digest(path) for path in sources}, indent=2) + "\n")

    lines = ["# Evaluation readiness audit", "", "Verified on 2026-10-09 against published PR #20 at `9d99966`.", "",
             "All four selected applications have working integrations and reference results. **All planned evaluation results are not yet ready.** The remaining gaps are listed below; controlled publication measurements are still outstanding.", "",
             "## Evidence inventory", "",
             "| Evidence | Verified coverage | Readiness |", "| --- | --- | --- |",
             "| Application references | 12 workloads, 334 raw timed samples across rsync, memcached, YAML and nginx | Available; hosted/shared reference |",
             "| Runtime microbenchmarks | 39 configurations × 5 repetitions = 195 raw samples | Available and recomputed from original artifact |",
             "| Latest runtime CI smoke | 39 configurations, one sample each at 9d99966's CI merge revision | Available separately; not a repeated reference |",
             "| P8 boundary validation microbenchmarks | All four boundaries, seven pairs each, 20,000 iterations per sample | CI summary verified; NaCl backend |",
             "| Memcached SP3 frequency | Six profiles, five observe successful checks | Write-heavy coverage missing |",
             "| Memcached six-scenario tracking-only comparison | Native/RLBox/InterSpec are present | Tracking-only cells missing |",
             "| wasm2c transition/copy/wrapper breakdown and boundary frequency | Planned in MEMCACHED_PERFORMANCE_PLAN.md | Not collected |",
             "| Controlled publication run | Application and microbenchmark protocols documented | Not run |", "",
             "Application numbers and baseline definitions: [SELECTED_EVALUATION_RESULTS.md](SELECTED_EVALUATION_RESULTS.md). CI at the published head passed core, memcached, P10 and nginx PR workflows. Nginx includes 24/24 cases, two-worker operation and two graceful reloads. The implementation stack remains unmerged.", "",
             "## Repeated runtime reference", "",
             "Source: memcached workflow 37593628863, five repetitions and 200,000 iterations for the ordinary check loops. This reference uses GCC 13.3.0 on a hosted x86_64 runner, with four CPUs available and no requested affinity. These are trusted runtime measurements with no sandbox crossing.", "",
             "| Operation | Live allocations | Median ns/op | Min to max ns/op |", "| --- | ---: | ---: | ---: |"]
    order = ["shared_lock", "metadata_lookup", "type_compare", "bounds_check", "check_live",
             "check_interior", "check_wrong_type", "remaining_bytes", "allocate", "allocate_from_site", "release"]
    for metric in order:
        row = next(row for row in summary if row["metric"] == metric and row["population"] in
                   ((16384,) if metric in ("allocate", "allocate_from_site", "release") else (2,)))
        lines.append(f"| {metric} | {row['population']} | {row['ns_per_op_median']:.2f} | {row['ns_per_op_min']:.2f} to {row['ns_per_op_max']:.2f} |")
    lines += ["", "Primitive costs are independent and must not be added. Use `check_live` for the direct production check cost. Allocation/release rows measure 16,384 operations per repetition.", "",
              "| Live allocations | Full check median ns/op |", "| ---: | ---: |"]
    for row in summary:
        if row["metric"] == "check_live":
            lines.append(f"| {row['population']} | {row['ns_per_op_median']:.2f} |")
    lines += ["", "| Trusted threads | Concurrent check median ns/op |", "| ---: | ---: |"]
    for row in summary:
        if row["metric"] == "check_concurrent":
            lines.append(f"| {row['threads']} | {row['ns_per_op_median']:.2f} |")
    lines += ["", "Concurrent ns/op divides total elapsed time by aggregate completed checks. It includes thread creation/join and contention over 4,096 tracked allocations, so it is not individual request latency or a linear scalability claim. Eight threads oversubscribe this four-CPU runner.", "",
              "The complete 39-row matrix is in [microbenchmark-summary.csv](evaluation/results/selected/microbenchmark-summary.csv), with five raw samples per row in the retained source. The latest single-pass CI smoke is kept separately and is not substituted into this repeated reference.", "",
              "## P8 boundary reference", "",
              "| Boundary | Tracking without final validation ns/op | Extended SP3 ns/op | Paired repetitions |", "| --- | ---: | ---: | ---: |"]
    for row in boundaries:
        lines.append(f"| {row['boundary']} | {float(row['baseline_median_ns']):.3f} | {float(row['extended_median_ns']):.3f} | {row['repetitions']} |")
    lines += ["", "These NaCl measurements reuse a valid U object and time trusted copy/use with versus without the final check. They retain allocation tracking in both modes and do not time a sandbox transition in each iteration. They do not replace the outstanding wasm2c Native-to-RLBox decomposition or measure total application overhead.", "",
              "Source: [CI run 37840970704](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37840970704), job 113529933478, artifact 11577986711. The timestamped summary is retained locally. Its paired raw CSV exists in that CI artifact; artifact download returned HTTP 403 in this workspace, so those pairs were not independently recomputed here. Runtime raw data above was independently verified from the already retained memcached archive.", "",
              "## Remaining results", ""]
    for index, gap in enumerate(gaps, 1):
        lines.append(f"{index}. {gap['detail']}")
    lines += ["", "The missing wasm2c breakdown is distinct from the completed P8 boundary validation measurements. An observed zero in a short diagnostic profile establishes missing coverage, not zero check overhead.", "",
              "## Reproduction", "", "```sh",
              "python3 tools/summarize_selected_evaluation.py --nginx-results evaluation/results/nginx-pcre/hosted-37835791042",
              "python3 tools/audit_evaluation_readiness.py", "```", "",
              "The audit verifies original artifact SHA-256 values and retained extracts, raw application source hashes, all runtime cells and repetitions, elapsed-time arithmetic, runtime summaries, and frequency count arithmetic. It fails on missing runtime samples or changed evidence. Readiness and source hashes are saved under `evaluation/results/selected/`.", ""]
    (ROOT / "EVALUATION_READINESS.md").write_text("\n".join(lines))
    print(f"Verified {app_samples} application samples, {len(raw)} repeated runtime samples, "
          f"{len(latest_runtime)} CI smoke samples and {len(boundaries)} boundary summaries; "
          f"{len(gaps)} outstanding result classes.")


if __name__ == "__main__":
    main()
