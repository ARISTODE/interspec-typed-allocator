#!/usr/bin/env python3
"""Count Nginx PCRE native events originating in pinned ngx_regex.c only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

NGINX_PIN = "1be0fb0c9f9bc3489c7b40576efd6afe6b2eccd5"
PCRE_PIN = "e67dabe61b327bd2d888954b0e74a7c9cfd0a195"


def original_sha(source, revision, files):
    assert subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"],
                                   text=True).strip() == revision
    result = {}
    for file in files:
        observed = (source / file).read_bytes()
        expected = subprocess.check_output(["git", "-C", str(source), "show", f"HEAD:{file}"])
        assert observed == expected, f"original upstream source changed: {source}/{file}"
        result[file] = hashlib.sha256(observed).hexdigest()
    return result


def source_location(filename, source):
    path = Path(filename)
    candidates = [path] if path.is_absolute() else [source / path, source / "objs" / path]
    for candidate in candidates:
        try:
            relative = candidate.resolve().relative_to(source)
            if candidate.is_file():
                return relative.as_posix()
        except (ValueError, OSError):
            pass
    return filename


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--nginx-source", type=Path, required=True)
    p.add_argument("--pcre-source", type=Path, required=True)
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    nginx_src, pcre_src = args.nginx_source.resolve(), args.pcre_source.resolve()
    hashes = {
        "nginx": original_sha(nginx_src, NGINX_PIN, ["src/core/ngx_regex.c"]),
        "pcre": original_sha(pcre_src, PCRE_PIN,
                              ["pcre_compile.c", "pcre_study.c"]),
    }
    parity = json.loads((args.output_dir / "native-parity.json").read_text())
    assert parity["parity"] == "pass"
    trace = args.output_dir / "nginx-original-pointer-events.jsonl"
    assert hashlib.sha256(trace.read_bytes()).hexdigest() == parity["sha256"]["raw_trace"]
    assert hashlib.sha256(args.binary.read_bytes()).hexdigest() == parity["sha256"]["traced_binary"]
    raw = [json.loads(s) for s in trace.read_text().splitlines() if s.strip()]
    assert raw and all(r["schema"] == 1 and r["api"] in
                       ("pcre_compile", "pcre_study") for r in raw)
    pcs = sorted({int(r["caller_pc"], 16) for r in raw})
    out = subprocess.check_output(["addr2line", "-e", str(args.binary), "-f", "-C",
                                  *[f"0x{pc-1:x}" for pc in pcs]],
                                 text=True).splitlines()
    assert len(out) == 2 * len(pcs)
    callsites = {}
    for i, pc in enumerate(pcs):
        function, raw_fileline = out[2*i:2*i+2]
        filename, _, number = raw_fileline.rpartition(":")
        try:
            line = int(number.split(" ", 1)[0])
        except ValueError:
            line = 0
        relative = source_location(filename, nginx_src)
        callsites[pc] = {"file": relative, "line": line, "function": function,
                         "accepted": relative == "src/core/ngx_regex.c" and line > 0}
    accepted = Counter()
    excluded = Counter()
    for event in raw:
        site = callsites[int(event["caller_pc"], 16)]
        key = (site["file"], site["line"], event["api"], event["role"], event["origin"])
        (accepted if site["accepted"] else excluded)[key] += 1
    assert accepted, "no upstream original Nginx PCRE calls attributed"
    assert sum(n for k, n in accepted.items()
               if k[3] == "t_to_u_errorptr_outparam" and k[4] == "stack") > 0
    assert sum(n for k, n in accepted.items()
               if k[3] == "t_to_u_erroffset_outparam" and k[4] == "stack") > 0
    assert sum(n for k, n in accepted.items()
               if k[3] == "u_to_t_error_string" and
               k[4] == "readonly_elf_image_candidate") > 0
    def sites(counter):
        return [{"file": k[0], "line": k[1], "api": k[2], "role": k[3],
                 "origin": k[4], "pointer_events": count}
                for k, count in sorted(counter.items())]
    summary = {
        "schema": 1, "benchmark": "nginx/pcre",
        "scope": "native original Nginx PCRE callsites, valid and error config",
        "coverage": "only direct pcre_compile/pcre_study args/returns, not exhaustive",
        "isolation": "not measured",
        "nginx_revision": NGINX_PIN, "pcre_revision": PCRE_PIN,
        "source_sha256": hashes, "native_parity": "pass",
        "raw_trace_sha256": parity["sha256"]["raw_trace"],
        "total_raw_records": len(raw),
        "accepted_original_source_pointer_events": sum(accepted.values()),
        "excluded_non_original_pointer_events": sum(excluded.values()),
        "input_pointer_events_by_origin": dict(sorted(Counter({
            origin: sum(n for k, n in accepted.items()
                        if k[3].startswith("t_to_u_") and k[4] == origin)
            for origin in {k[4] for k in accepted if k[3].startswith("t_to_u_")}
        }).items())),
        "error_string_return_events_by_origin": dict(sorted(Counter({
            origin: sum(n for k, n in accepted.items()
                        if k[3] == "u_to_t_error_string" and k[4] == origin)
            for origin in {k[4] for k in accepted if k[3] == "u_to_t_error_string"}
        }).items())),
        "original_source_sites": sites(accepted),
        "excluded_sites": sites(excluded),
    }
    (args.output_dir / "source-only-runtime-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"native_parity": "pass",
                      "accepted_pointer_events": summary["accepted_original_source_pointer_events"],
                      "input_origin_counts": summary["input_pointer_events_by_origin"],
                      "error_string_origins": summary["error_string_return_events_by_origin"]}))


if __name__ == "__main__":
    main()
