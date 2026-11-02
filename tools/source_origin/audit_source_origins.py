#!/usr/bin/env python3
"""Conservative source-only census on pinned upstream application code.

The two result categories must never be combined for a paper prevalence claim:
boundary_use records refer to an original application's pointer-valued API
expression; library_candidate records describe a library producer that may
never be exposed or consumed by T. Neither category is a dynamic frequency.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

PINS = {
    "nginx": "1be0fb0c9f9bc3489c7b40576efd6afe6b2eccd5",
    "pcre": "e67dabe61b327bd2d888954b0e74a7c9cfd0a195",
    "rsync": "7c20b077c980036a19587701cec320cc88e42a4a",
    "libyaml": "90a56d4500aa1a1798514c5cb55c3ad4cb095f94",
    "memcached": "2d51e364799bc9698bd4b11728ea978cea12da6e",
}

def sources(root, repo, file):
    return (root / repo / file).read_text(encoding="utf-8", errors="replace")

def strip_comments(s):
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/',
                  lambda m: re.sub(r'[^\n]', ' ', m.group()), s)

def calls(original, name):
    """Get source line and top-level C arguments, retaining string literals."""
    text = strip_comments(original)
    for m in re.finditer(r'\b' + re.escape(name) + r'\s*\(', text):
        depth, start, quote, escaped = 0, m.end(), None, False
        args = []
        for i in range(m.end() - 1, len(text)):
            c = text[i]
            if quote:
                if escaped: escaped = False
                elif c == '\\': escaped = True
                elif c == quote: quote = None
                continue
            if c in "\"'": quote = c
            elif c == '(': depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    args.append(text[start:i].strip())
                    yield original.count('\n', 0, m.start()) + 1, args
                    break
            elif c == ',' and depth == 1:
                args.append(text[start:i].strip())
                start = i + 1

def study(root):
    for repo, sha in PINS.items():
        found = subprocess.check_output(
            ["git", "-C", str(root / repo), "rev-parse", "HEAD"], text=True).strip()
        if found != sha:
            raise ValueError(f"{repo} not pinned: {found} != {sha}")

    records = []
    def add(kind, app, origin, repo, path, line, expression):
        records.append(dict(kind=kind, boundary=app, origin=origin,
                            upstream=repo, path=path, line=line, expression=expression))

    nginx_path = "src/core/ngx_regex.c"
    nginx = sources(root, "nginx", nginx_path)
    compile_calls = [(ln, a) for ln, a in calls(nginx, "pcre_compile")
                     if len(a) == 5 and a[2] == "&errstr" and a[3] == "&erroff"]
    study_calls = [(ln, a) for ln, a in calls(nginx, "pcre_study")
                   if len(a) == 3 and a[2] == "&errstr"]
    if len(compile_calls) != 1 or len(study_calls) != 1:
        raise ValueError("upstream Nginx call-site shape changed")
    if "errstr, &rc->pattern)" not in nginx or "errstr, elts[i].name)" not in nginx:
        raise ValueError("original Nginx PCRE error strings not consumed")
    for name, line, origin in (
        ("&errstr", compile_calls[0][0], "T_stack"),
        ("&erroff", compile_calls[0][0], "T_stack"),
        ("pcre_compile:errorptr", compile_calls[0][0], "U_static"),
        ("&errstr", study_calls[0][0], "T_stack"),
        ("pcre_study:errorptr", study_calls[0][0], "U_static"),
    ):
        add("boundary_use", "nginx_pcre", origin, "nginx", nginx_path, line, name)

    compile_src = sources(root, "pcre", "pcre_compile.c")
    if "static const char error_texts[]" not in compile_src or "const char *s = error_texts;" not in compile_src:
        raise ValueError("PCRE static error text not confirmed")
    for m in re.finditer(r'\*errorptr\s*=\s*find_error_text\s*\(', compile_src):
        add("library_candidate", "nginx_pcre", "U_static", "pcre", "pcre_compile.c",
            compile_src.count('\n', 0, m.start()) + 1, "*errorptr")
    study_src = sources(root, "pcre", "pcre_study.c")
    for m in re.finditer(r'\*errorptr\s*=\s*"(?:\\.|[^"\\])*"\s*;', strip_comments(study_src)):
        add("library_candidate", "nginx_pcre", "U_static", "pcre", "pcre_study.c",
            study_src.count('\n', 0, m.start()) + 1, "*errorptr")

    popt = sources(root, "rsync", "popt/popt.c")
    if "poptStrerror(const int error)" not in popt or 'POPT_("unknown option")' not in popt:
        raise ValueError("original popt error producer missing")
    for path in ("options.c", "tls.c"):
        src = sources(root, "rsync", path)
        # The deployed P4c bridge isolates poptBadOption and copies its return.
        # The original source invokes poptStrerror too, but the P4c build
        # deliberately leaves this standalone helper in trusted host libpopt.
        for line, args in calls(src, "poptBadOption"):
            if len(args) == 2:
                add("boundary_use", "rsync_popt", "U_argv_or_alias_pointer",
                    "rsync", path, line, "poptBadOption")
        for line, args in calls(src, "poptStrerror"):
            if len(args) == 1:
                add("host_helper_excluded", "rsync_popt", "T_literal_or_i18n",
                    "rsync", path, line, "poptStrerror")

    logger = sources(root, "memcached", "logger.c")
    if "char scratch[LOGGER_PARSE_SCRATCH];" not in logger:
        raise ValueError("memcached stack scratch origin missing")
    for line, args in calls(logger, "bipbuf_offer"):
        if len(args) != 3: continue
        if re.search(r'\bscratch\b', args[1]):
            add("boundary_use", "memcached_bipbuffer", "T_stack",
                "memcached", "logger.c", line, args[1])
        elif '"OK\\r\\n"' in args[1]:
            add("boundary_use", "memcached_bipbuffer", "T_static",
                "memcached", "logger.c", line, args[1])
    for path in ("logger.c", "items.c"):
        src = sources(root, "memcached", path)
        for line, args in calls(src, "bipbuf_peek_all"):
            if len(args) == 2 and args[1] in ("&size", "&data_size"):
                add("boundary_use", "memcached_bipbuffer", "T_stack",
                    "memcached", path, line, args[1])

    yaml_setters = {
        "yaml_parser_set_parser_error": (1,),
        "yaml_parser_set_parser_error_context": (1, 3),
        "yaml_parser_set_scanner_error": (1, 3),
        "yaml_parser_set_reader_error": (1,),
        "yaml_parser_set_composer_error": (1,),
        "yaml_parser_set_composer_error_context": (1, 3),
    }
    for path in ("src/parser.c", "src/scanner.c", "src/reader.c", "src/loader.c"):
        src = sources(root, "libyaml", path)
        for func, positions in yaml_setters.items():
            for line, args in calls(src, func):
                for index in positions:
                    if len(args) > index and re.search(r'"(?:\\.|[^"\\])*"', args[index]):
                        add("library_candidate", "yaml_libyaml", "U_static",
                            "libyaml", path, line, f"{func}:argument_{index}")

    result = Counter((r["kind"], r["boundary"], r["origin"]) for r in records)
    expected = {
        ("library_candidate", "nginx_pcre", "U_static"): 11,
        ("library_candidate", "yaml_libyaml", "U_static"): 103,
        ("boundary_use", "nginx_pcre", "T_stack"): 3,
        ("boundary_use", "nginx_pcre", "U_static"): 2,
        ("boundary_use", "rsync_popt", "U_argv_or_alias_pointer"): 3,
        ("host_helper_excluded", "rsync_popt", "T_literal_or_i18n"): 3,
        ("boundary_use", "memcached_bipbuffer", "T_stack"): 5,
        ("boundary_use", "memcached_bipbuffer", "T_static"): 1,
    }
    if dict(result) != expected:
        raise ValueError(f"unexpected source site counts: {dict(result)}")
    return {
        "schema": 1, "scope": "original pinned upstream source only",
        "description": "Source expressions, NOT runtime frequencies or complete coverage",
        "pinned_revisions": PINS,
        "boundary_uses": sum(r["kind"] == "boundary_use" for r in records),
        "library_candidates_excluded": sum(r["kind"] == "library_candidate" for r in records),
        "host_helpers_excluded": sum(r["kind"] == "host_helper_excluded" for r in records),
        "counts": [{"kind": k, "boundary": b, "origin": o, "sites": n}
                   for (k, b, o), n in sorted(result.items())],
        "records": sorted(records, key=lambda r: (r["kind"], r["boundary"],
                         r["upstream"], r["path"], r["line"], r["expression"]))
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = study(args.root.resolve())
    rendered = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
        print(json.dumps({"boundary_uses": result["boundary_uses"],
                          "library_candidates_excluded": result["library_candidates_excluded"],
                          "host_helpers_excluded": result["host_helpers_excluded"],
                          "output": str(args.output)}))
    else:
        print(rendered)

if __name__ == "__main__":
    main()
