#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


def hash_type(name):
    value = 0
    for byte in name.encode():
        value = (129 * value + byte) & ((1 << 64) - 1)
    return value


def macro(name):
    return re.sub(r"[^A-Za-z0-9]", "_", name).upper()


def cpp(name):
    parts = re.split(r"[^A-Za-z0-9]+", name)
    return "".join(part[:1].upper() + part[1:] for part in parts if part)


def function_body(source, function):
    match = re.search(r"\b" + re.escape(function) + r"\s*\([^)]*\)\s*\{", source)
    if not match:
        raise ValueError(f"function not found: {function}")
    depth = 1
    pos = match.end()
    while pos < len(source) and depth:
        depth += (source[pos] == "{") - (source[pos] == "}")
        pos += 1
    if depth:
        raise ValueError(f"unterminated function: {function}")
    return match.end(), pos - 1


def source_offset(source, line, column, end=False):
    if line < 1 or column < 1:
        raise ValueError("source locations are one-based")
    lines = source.splitlines(keepends=True)
    if line > len(lines):
        raise ValueError(f"source line out of range: {line}")
    text = lines[line - 1]
    visible = text[:-1] if text.endswith("\n") else text
    if visible.endswith("\r"):
        visible = visible[:-1]
    max_column = len(visible) + (1 if end else 0)
    if column > max_column:
        raise ValueError(f"source column out of range: {line}:{column}")
    base = sum(len(part) for part in lines[: line - 1])
    return base + column if end else base + column - 1


def instrument_site(source, allocation):
    site = allocation["site"]
    start = source_offset(
        source, int(site["start_line"]), int(site["start_column"])
    )
    end = source_offset(
        source, int(site["end_line"]), int(site["end_column"]), end=True
    )
    if end <= start:
        raise ValueError(f"invalid allocation site in {allocation['function']}")

    function_start, function_end = function_body(source, allocation["function"])
    if start < function_start or end > function_end:
        raise ValueError(
            f"allocation site escapes function {allocation['function']}"
        )

    call = source[start:end]
    match = re.fullmatch(r"\s*malloc\s*\((.*)\)\s*", call, re.DOTALL)
    if not match:
        raise ValueError(
            f"allocation site in {allocation['function']} is not a direct malloc: {call!r}"
        )

    size_expr = match.group(1).strip()
    if not size_expr:
        raise ValueError(f"empty malloc size in {allocation['function']}")

    type_id = f"INTERSPEC_TYPE_ID_{macro(allocation['type'])}"
    replacement = (
        f"(void*)(uintptr_t)typed_alloc((uint32_t)({size_expr}), {type_id})"
    )
    return source[:start] + replacement + source[end:]


def instrument_legacy(source, allocation):
    start, end = function_body(source, allocation["function"])
    body = source[start:end]
    type_name = allocation["type"]
    type_id = f"INTERSPEC_TYPE_ID_{macro(type_name)}"

    old = f"(struct {type_name}*)malloc(sizeof(struct {type_name}))"
    if body.count(old) == 1:
        new = (
            f"(struct {type_name}*)(uintptr_t)typed_alloc(sizeof(struct {type_name}), "
            f"{type_id})"
        )
        body = body.replace(old, new, 1)
    else:
        sizeof_pattern = re.compile(
            r"malloc\s*\(\s*sizeof\s*\(\s*\*\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\)"
        )
        sizeof_matches = list(sizeof_pattern.finditer(body))
        if len(sizeof_matches) == 1:
            var = sizeof_matches[0].group(1)
            new = f"(void*)(uintptr_t)typed_alloc(sizeof(*{var}), {type_id})"
            body = (
                body[:sizeof_matches[0].start()]
                + new
                + body[sizeof_matches[0].end():]
            )
        else:
            # Backward-compatible fallback for hand-written policies that do
            # not yet carry a CodeQL source span.  P5 source-derived policies
            # use instrument_site(), which supports arbitrary malloc sizes.
            plain_pattern = re.compile(
                r"malloc\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)"
            )
            plain_matches = list(plain_pattern.finditer(body))
            if len(plain_matches) != 1:
                raise ValueError(
                    f"expected one typed malloc in {allocation['function']}"
                )
            size_expr = plain_matches[0].group(1)
            new = (
                f"(void*)(uintptr_t)typed_alloc((uint32_t)({size_expr}), "
                f"{type_id})"
            )
            body = (
                body[:plain_matches[0].start()]
                + new
                + body[plain_matches[0].end():]
            )

    return source[:start] + body + source[end:]


def generate(policy, source):
    ids = {name: index + 1 for index, name in enumerate(policy["types"])}
    if len(ids) != len(policy["types"]):
        raise ValueError("duplicate type")

    hashes = {}
    for name in ids:
        value = hash_type(name)
        if value in hashes:
            raise ValueError(
                f"TypeHash collision between {hashes[value]!r} and {name!r}"
            )
        hashes[value] = name

    for allocation in policy["allocations"]:
        if allocation["type"] not in ids:
            raise ValueError(f"unknown allocation type: {allocation['type']}")

    precise = [a for a in policy["allocations"] if "site" in a]
    legacy = [a for a in policy["allocations"] if "site" not in a]
    precise.sort(
        key=lambda a: (
            int(a["site"]["start_line"]), int(a["site"]["start_column"])
        ),
        reverse=True,
    )
    for allocation in precise:
        source = instrument_site(source, allocation)
    for allocation in legacy:
        source = instrument_legacy(source, allocation)

    u = ["#pragma once", "", "#include <stdint.h>", ""]
    for name, type_id in ids.items():
        u.append(f"#define INTERSPEC_TYPE_ID_{macro(name)} UINT32_C({type_id})")
    u.append("")

    t = [
        "#pragma once",
        "",
        '#include "interspec/runtime.h"',
        "#include <limits>",
        "",
        "namespace interspec::generated {",
        "",
        "struct AccessPolicy {",
        "  uint64_t type_hash;",
        "  size_t offset;",
        "  size_t bytes;",
        "};",
        "",
        "struct CheckedAccess {",
        "  CheckResult result;",
        "  uintptr_t address;",
        "  size_t bytes;",
        "};",
        "",
    ]
    for name, type_id in ids.items():
        ident = cpp(name)
        t += [
            f"constexpr TypeId kTypeId{ident} = {type_id};",
            f"constexpr uint64_t kTypeHash{ident} = UINT64_C({hash_type(name)});",
        ]
    t += ["", "inline bool register_types(Runtime& runtime)", "{", "  bool ok = true;"]
    for name in ids:
        ident = cpp(name)
        t.append(f"  ok = runtime.register_type(kTypeId{ident}, kTypeHash{ident}) && ok;")
    t += ["  return ok;", "}", ""]

    for use in policy["uses"]:
        if use["type"] not in ids:
            raise ValueError(f"unknown use type: {use['type']}")
        use_ident = cpp(use["name"])
        type_ident = cpp(use["type"])
        offset = int(use["offset"])
        size = int(use["bytes"])
        if offset < 0 or size < 0:
            raise ValueError(f"negative access range: {use['name']}")
        t += [
            f"constexpr AccessPolicy kUse{use_ident}{{",
            f"  kTypeHash{type_ident}, {offset}, {size}}};",
        ]
    t += [
        "",
        "inline CheckedAccess checked_access(const Runtime& runtime,",
        "                                    uintptr_t base,",
        "                                    AccessPolicy policy)",
        "{",
        "  if (policy.offset > std::numeric_limits<size_t>::max() - policy.bytes)",
        "    return {CheckResult::out_of_bounds, 0, 0};",
        "  const size_t extent = policy.offset + policy.bytes;",
        "  const CheckResult result = runtime.check(base, extent, policy.type_hash);",
        "  if (result != CheckResult::ok) return {result, 0, 0};",
        "  return {result, base + policy.offset, policy.bytes};",
        "}",
        "",
        "inline CheckResult check(const Runtime& runtime, uintptr_t base, AccessPolicy policy)",
        "{",
        "  return checked_access(runtime, base, policy).result;",
        "}",
        "",
        "}  // namespace interspec::generated",
        "",
    ]
    return source, "\n".join(u), "\n".join(t)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    policy = json.loads(Path(args.policy).read_text())
    source_path = Path(args.source)
    source = source_path.read_text()
    instrumented, u_header, t_header = generate(policy, source)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / source_path.name).write_text(instrumented)
    (out / "interspec_u_policy.h").write_text(u_header)
    (out / "interspec_t_policy.h").write_text(t_header)


if __name__ == "__main__":
    main()
