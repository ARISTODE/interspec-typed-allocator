#!/usr/bin/env python3
"""Count classified pointer events from normal native-versus-isolated workloads.

These are observations of the trusted adapter and checked U pointer uses,
not an inventory of every pointer stored inside U. T pointers are copied or
tokenized and their numerical addresses never cross into U.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

CASES = {
    "rsync_popt": [
        "archive_transfer-integrated.stderr",
        "size_filter-integrated.stderr",
        "dry_run-integrated.stderr",
        "update_backup-integrated.stderr",
        "invalid_numeric_option-integrated.stderr",
        "unknown_option-integrated.stderr",
    ],
    "yaml_libyaml": ["correctness-extended_sp3.stderr"],
    "nginx_pcre": ["interspec-w0/stderr.log", "interspec-w2/stderr.log"],
    "memcached_bipbuffer": ["interspec/normal.stderr"],
}
REQUIRED = {
    "rsync_popt": {"string_copy_source", "shadow_destination", "checked_string_result"},
    "yaml_libyaml": {"document_copy_source", "checked_scalar_result"},
    "nginx_pcre": {"pattern_or_subject_copy_source", "capture_offsets_output", "checked_input_staging"},
    "memcached_bipbuffer": {"offer_copy_source", "push_copy_source", "lru_item_tokenized", "peek_all_size_output"},
}
ORIGINS = {
    "t_stack", "t_image_static", "t_brk_heap_vma", "t_other_stack_vma",
    "t_file_vma", "t_named_vma", "t_anon_vma", "t_unmapped",
    "unknown", "null", "u_tracked_heap", "u_unclassified",
}
DIRECTIONS = {"t_to_u", "t_adapter_only", "u_to_t"}


def parse_record(line, path, number, boundary):
    if not line.startswith("INTERSPEC_POINTER_CENSUS "):
        return None
    try:
        fields = dict(part.split("=", 1) for part in line.split()[1:])
        expected = {"schema", "pid", "boundary", "direction", "site", "storage", "address", "result"}
        if set(fields) != expected or fields["schema"] != "1":
            raise ValueError("invalid schema or fields")
        if fields["boundary"] != boundary:
            raise ValueError("wrong boundary")
        if fields["direction"] not in DIRECTIONS or fields["storage"] not in ORIGINS:
            raise ValueError("unknown category")
        if fields["direction"] == "u_to_t" and not fields["storage"].startswith("u_"):
            raise ValueError("sandbox pointer mislabeled as T")
        if fields["direction"] != "u_to_t" and fields["storage"].startswith("u_"):
            raise ValueError("trusted pointer mislabeled as U")
        if int(fields["pid"]) < 1 or int(fields["address"], 16) < 0:
            raise ValueError("invalid pid or address")
        if not fields["site"].replace("_", "").isalnum():
            raise ValueError("invalid site")
        if fields["result"] not in ("observed", "accepted", "rejected_or_untracked"):
            raise ValueError("invalid result")
        return fields
    except ValueError as error:
        raise ValueError(f"{path}:{number}: malformed census: {error}") from error


def summarize(boundary, root):
    if boundary not in CASES:
        raise ValueError("unknown boundary")
    root = Path(root)
    sites = Counter()
    storage = Counter()
    directions = Counter()
    cases = []
    for relative in CASES[boundary]:
        path = root / relative
        raw = path.read_bytes()
        count = 0
        for number, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1):
            row = parse_record(line, path, number, boundary)
            if row is None:
                continue
            count += 1
            sites[(row["direction"], row["site"], row["storage"])] += 1
            storage[row["storage"]] += 1
            directions[row["direction"]] += 1
        cases.append({"log": relative, "sha256": hashlib.sha256(raw).hexdigest(),
                      "observations": count})
    missing = REQUIRED[boundary] - {key[1] for key in sites}
    if missing:
        raise ValueError(f"missing mandatory sites: {sorted(missing)}")
    trusted = directions["t_to_u"] + directions["t_adapter_only"]
    stack = storage["t_stack"]
    image = storage["t_image_static"]
    return {
        "schema": 1,
        "boundary": boundary,
        "scope": "normal correctness cases; adapter pointer arguments and copies; checked sandbox results",
        "limitations": [
            "t_stack identifies only the executing T thread's stack range",
            "t_image_static denotes readable nonexecutable ELF image storage, not proven named globals",
            "VMA classes identify mapping regions, not allocation identity, object type, or lifetime",
            "t_anon_vma may include malloc arenas and other-thread stacks; it is not a proof of heap ownership",
            "unknown means maps inspection unavailable; t_unmapped means no covering VMA was found",
            "uninstrumented pointers are not counted",
            "u_tracked_heap requires a successful SP3 check; U stack and globals remain unclassified",
            "counts denote pointer observations, not unique objects",
            "T pointer addresses remain in T and are copied or tokenized, not passed raw into U",
        ],
        "total_observations": sum(directions.values()),
        "trusted_observations": trusted,
        "trusted_stack_observations": stack,
        "trusted_image_static_observations": image,
        "trusted_unknown_or_null_observations": storage["unknown"] + storage["null"],
        "trusted_unmapped_observations": storage["t_unmapped"],
        "trusted_vma_attributed_observations": sum(
            storage[origin] for origin in ("t_brk_heap_vma", "t_other_stack_vma",
                                         "t_file_vma", "t_named_vma", "t_anon_vma")
        ),
        "trusted_stack_or_image_static_fraction": (stack + image) / trusted if trusted else None,
        "by_direction": dict(sorted(directions.items())),
        "by_storage": dict(sorted(storage.items())),
        "by_site": [{"direction": direction, "site": site, "storage": origin,
                     "observations": count}
                    for (direction, site, origin), count in sorted(sites.items())],
        "cases": cases,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--app", required=True, choices=sorted(CASES))
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    report = summarize(args.app, args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    # Make the full provenance-grouped stats inspectable even without ZIP access.
    print("INTERSPEC_POINTER_SUMMARY " + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

