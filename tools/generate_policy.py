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


def instrument(source, allocation):
    start, end = function_body(source, allocation["function"])
    body = source[start:end]
    type_name = allocation["type"]
    old = f"(struct {type_name}*)malloc(sizeof(struct {type_name}))"
    new = (
        f"(struct {type_name}*)(uintptr_t)typed_alloc(sizeof(struct {type_name}), "
        f"INTERSPEC_TYPE_ID_{macro(type_name)})"
    )
    if body.count(old) != 1:
        raise ValueError(f"expected one typed malloc in {allocation['function']}")
    return source[:start] + body.replace(old, new, 1) + source[end:]


def generate(policy, source):
    ids = {name: index + 1 for index, name in enumerate(policy["types"])}
    if len(ids) != len(policy["types"]):
        raise ValueError("duplicate type")

    for allocation in policy["allocations"]:
        if allocation["type"] not in ids:
            raise ValueError(f"unknown allocation type: {allocation['type']}")
        source = instrument(source, allocation)

    u = ["#pragma once", "", "#include <stdint.h>", ""]
    for name, type_id in ids.items():
        u.append(f"#define INTERSPEC_TYPE_ID_{macro(name)} UINT32_C({type_id})")
    u.append("")

    t = [
        "#pragma once",
        "",
        '#include "interspec/runtime.h"',
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
        "  const CheckResult result =",
        "      runtime.check(base, policy.offset + policy.bytes, policy.type_hash);",
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
    source = Path(args.source).read_text()
    instrumented, u_header, t_header = generate(policy, source)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "typed_poc_untrusted.c").write_text(instrumented)
    (out / "interspec_u_policy.h").write_text(u_header)
    (out / "interspec_t_policy.h").write_text(t_header)


if __name__ == "__main__":
    main()
