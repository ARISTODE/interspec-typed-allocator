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


def symbol(name):
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


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


def malloc_call_extent(source, anchor_start, anchor_end):
    """Expand an analyzed malloc span to the complete malloc(...) call."""
    if anchor_end <= anchor_start or not source.startswith("malloc", anchor_start):
        raise ValueError(
            f"allocation anchor does not start at malloc: {source[anchor_start:anchor_end]!r}"
        )

    name_end = anchor_start + len("malloc")
    if name_end > anchor_end:
        raise ValueError("allocation span truncates the malloc token")

    pos = name_end
    while pos < len(source) and source[pos].isspace():
        pos += 1
    if pos >= len(source) or source[pos] != "(":
        raise ValueError("malloc anchor is not followed by an argument list")

    open_paren = pos
    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    pos = open_paren

    while pos < len(source):
        ch = source[pos]
        nxt = source[pos + 1] if pos + 1 < len(source) else ""

        if line_comment:
            if ch == "\n":
                line_comment = False
            pos += 1
            continue

        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                pos += 2
            else:
                pos += 1
            continue

        if quote is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            pos += 1
            continue

        if ch == "/" and nxt == "/":
            line_comment = True
            pos += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            pos += 2
            continue
        if ch in {'"', "'"}:
            quote = ch
            pos += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                argument = source[open_paren + 1:pos].strip()
                if not argument:
                    raise ValueError("empty malloc size expression")
                call_end = pos + 1
                if anchor_end > call_end and source[call_end:anchor_end].strip():
                    raise ValueError(
                        "allocation span extends past the selected malloc call"
                    )
                return anchor_start, call_end, argument
            if depth < 0:
                break
        pos += 1

    raise ValueError("unterminated malloc argument list")


def site_symbols(allocation, site_id):
    stem = symbol(allocation["function"])
    prefix = f"interspec_alloc_site_{stem}_{site_id}"
    return prefix + "_begin", prefix + "_end"


def instrument_site(source, allocation, site_id):
    site = allocation["site"]
    anchor_start = source_offset(
        source, int(site["start_line"]), int(site["start_column"])
    )
    anchor_end = source_offset(
        source, int(site["end_line"]), int(site["end_column"]), end=True
    )
    if anchor_end <= anchor_start:
        raise ValueError(f"invalid allocation site in {allocation['function']}")

    function_start, function_end = function_body(source, allocation["function"])
    if anchor_start < function_start or anchor_end > function_end:
        raise ValueError(
            f"allocation site escapes function {allocation['function']}"
        )

    call_start, call_end, size_expr = malloc_call_extent(
        source, anchor_start, anchor_end
    )
    if call_end > function_end:
        raise ValueError(
            f"malloc call escapes function {allocation['function']}"
        )

    begin_symbol, end_symbol = site_symbols(allocation, site_id)
    replacement = (
        "({ "
        f"uint32_t __interspec_size = (uint32_t)({size_expr}); "
        "uint32_t __interspec_ptr = 0; "
        f"__asm__ __volatile__(\".globl {begin_symbol}\\n{begin_symbol}:\" ::: \"memory\"); "
        "__interspec_ptr = INTERSPEC_SITE_ALLOC(__interspec_size); "
        f"__asm__ __volatile__(\".globl {end_symbol}\\n{end_symbol}:\" ::: \"memory\"); "
        "(void*)(uintptr_t)__interspec_ptr; })"
    )
    return source[:call_start] + replacement + source[call_end:]


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

    site_ids = {}
    next_site_id = 1
    for index, allocation in enumerate(policy["allocations"]):
        if allocation["type"] not in ids:
            raise ValueError(f"unknown allocation type: {allocation['type']}")
        if "site" in allocation:
            site_ids[index] = next_site_id
            next_site_id += 1

    precise = [
        (index, allocation)
        for index, allocation in enumerate(policy["allocations"])
        if "site" in allocation
    ]
    legacy = [
        allocation
        for allocation in policy["allocations"]
        if "site" not in allocation
    ]
    precise.sort(
        key=lambda entry: (
            int(entry[1]["site"]["start_line"]),
            int(entry[1]["site"]["start_column"]),
        ),
        reverse=True,
    )
    for index, allocation in precise:
        source = instrument_site(source, allocation, site_ids[index])
    for allocation in legacy:
        source = instrument_legacy(source, allocation)

    u = [
        "#pragma once",
        "",
        "#include <stdint.h>",
        '#include "interspec_site_allocator.h"',
        "",
    ]
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
        "struct AllocationSitePolicy {",
        "  SiteId site_id;",
        "  TypeId type_id;",
        "  const char* begin_symbol;",
        "  const char* end_symbol;",
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

    site_entries = []
    for index, allocation in enumerate(policy["allocations"]):
        if index not in site_ids:
            continue
        site_id = site_ids[index]
        type_ident = cpp(allocation["type"])
        begin_symbol, end_symbol = site_symbols(allocation, site_id)
        site_entries.append(
            (site_id, type_ident, begin_symbol, end_symbol)
        )

    t.append(f"constexpr size_t kAllocationSiteCount = {len(site_entries)};")
    if site_entries:
        t.append("constexpr AllocationSitePolicy kAllocationSites[] = {")
        for site_id, type_ident, begin_symbol, end_symbol in site_entries:
            t.append(
                f'  {{{site_id}, kTypeId{type_ident}, "{begin_symbol}", "{end_symbol}"}},'
            )
        t += ["};", ""]
        t += [
            "template<typename Resolver>",
            "inline bool register_allocation_sites(Runtime& runtime, Resolver resolve)",
            "{",
            "  for (const auto& site : kAllocationSites) {",
            "    const uintptr_t begin = resolve(site.begin_symbol);",
            "    const uintptr_t end = resolve(site.end_symbol);",
            "    if (!begin || !end ||",
            "        !runtime.register_allocation_site(site.site_id, begin, end, site.type_id))",
            "      return false;",
            "  }",
            "  return true;",
            "}",
            "",
        ]
    else:
        t += [
            "template<typename Resolver>",
            "inline bool register_allocation_sites(Runtime&, Resolver)",
            "{",
            "  return true;",
            "}",
            "",
        ]

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
