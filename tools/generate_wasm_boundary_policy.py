#!/usr/bin/env python3

import argparse
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.generate_policy import (
    cpp,
    function_body,
    hash_type,
    macro,
    malloc_call_extent,
    source_offset,
    symbol,
)


def c_stem(namespace_name):
    return symbol(namespace_name).lower()


def import_stem(namespace_name):
    value = cpp(namespace_name)
    if not value:
        raise ValueError("empty wasm namespace")
    return value


def site_import_name(namespace_name, site_id):
    return f"interspecWasmAlloc{import_stem(namespace_name)}Site{site_id}"


def site_c_name(namespace_name, site_id):
    return f"interspec_wasm_alloc_{c_stem(namespace_name)}_site_{site_id}"


def helper_macro(name):
    return f"INTERSPEC_SITE_{macro(name)}_ALLOC"


def instrument_site(source, allocation, site_id, namespace_name):
    site = allocation["site"]
    anchor_start = source_offset(
        source, int(site["start_line"]), int(site["start_column"])
    )
    anchor_end = source_offset(
        source, int(site["end_line"]), int(site["end_column"]), end=True
    )
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
    alloc = site_c_name(namespace_name, site_id)
    replacement = (
        f"(void*)(uintptr_t){alloc}((uint32_t)({size_expr}))"
    )
    return source[:call_start] + replacement + source[call_end:]


def prepare_policy(policy, boundary):
    composed = copy.deepcopy(policy)
    boundary = boundary or {}
    known_types = set(composed["types"])
    for type_name in boundary.get("types", []):
        if not isinstance(type_name, str) or not type_name:
            raise ValueError("boundary type names must be non-empty strings")
        if type_name not in known_types:
            composed["types"].append(type_name)
            known_types.add(type_name)
    return composed


def site_records(policy, boundary, namespace_name):
    records = []
    precise_count = 0
    for allocation in policy["allocations"]:
        if "site" not in allocation:
            raise ValueError(
                "wasm-direct provenance requires a precise source allocation site"
            )
        precise_count += 1
        records.append({
            "site_id": precise_count,
            "type": allocation["type"],
            "import_name": site_import_name(namespace_name, precise_count),
            "c_name": site_c_name(namespace_name, precise_count),
            "helper": False,
        })
    seen = set()
    for index, helper in enumerate((boundary or {}).get("helper_sites", []), start=1):
        name = helper["name"]
        if name in seen:
            raise ValueError(f"duplicate helper site: {name}")
        seen.add(name)
        site_id = precise_count + index
        records.append({
            "site_id": site_id,
            "type": helper["type"],
            "import_name": site_import_name(namespace_name, site_id),
            "c_name": site_c_name(namespace_name, site_id),
            "helper": True,
            "helper_name": name,
        })
    return records, precise_count


def generate_u_header(types, records):
    ids = {name: index + 1 for index, name in enumerate(types)}
    lines = [
        "#pragma once",
        "",
        "#include <stdint.h>",
        "",
        "#if defined(__wasm__)",
        "#  define INTERSPEC_WASM_IMPORT(_module, _name) \\",
        "    __attribute__((import_module(_module), import_name(_name)))",
        "#else",
        "#  define INTERSPEC_WASM_IMPORT(_module, _name)",
        "#endif",
        "",
    ]
    for name, type_id in ids.items():
        lines.append(f"#define INTERSPEC_TYPE_ID_{macro(name)} UINT32_C({type_id})")
    lines.append("")
    for record in records:
        lines += [
            f"extern uint32_t {record['c_name']}(uint32_t size)",
            f"  INTERSPEC_WASM_IMPORT(\"env\", \"{record['import_name']}\");",
        ]
        if record["helper"]:
            lines += [
                f"#define {helper_macro(record['helper_name'])}(_size) \\",
                f"  {record['c_name']}((uint32_t)(_size))",
            ]
        lines.append("")
    lines += [
        "extern uint32_t interspec_wasm_release(uint32_t ptr)",
        "  INTERSPEC_WASM_IMPORT(\"env\", \"interspecWasmRelease\");",
        "extern uint32_t interspec_wasm_size(uint32_t ptr)",
        "  INTERSPEC_WASM_IMPORT(\"env\", \"interspecWasmSize\");",
        "extern uint32_t interspec_wasm_reallocate(uint32_t ptr, uint32_t size)",
        "  INTERSPEC_WASM_IMPORT(\"env\", \"interspecWasmReallocate\");",
        "",
    ]
    return "\n".join(lines)


def generate_t_header(policy, records, precise_count, namespace_name):
    ids = {name: index + 1 for index, name in enumerate(policy["types"])}
    hashes = {}
    for name in ids:
        value = hash_type(name)
        if value in hashes:
            raise ValueError(
                f"TypeHash collision between {hashes[value]!r} and {name!r}"
            )
        hashes[value] = name

    lines = [
        "#pragma once",
        "",
        '#include "interspec/runtime.h"',
        "#include <limits>",
        "",
        f"namespace {namespace_name} {{",
        "",
        "struct AccessPolicy {",
        "  uint64_t type_hash;",
        "  size_t offset;",
        "  size_t bytes;",
        "};",
        "",
        "struct WasmAllocationSitePolicy {",
        "  SiteId site_id;",
        "  TypeId type_id;",
        "  const char* import_name;",
        "  bool helper;",
        "};",
        "",
    ]
    for name, type_id in ids.items():
        ident = cpp(name)
        lines += [
            f"constexpr TypeId kTypeId{ident} = {type_id};",
            f"constexpr uint64_t kTypeHash{ident} = UINT64_C({hash_type(name)});",
        ]
    lines += [
        "",
        "inline bool register_types(Runtime& runtime)",
        "{",
        "  bool ok = true;",
    ]
    for name in ids:
        ident = cpp(name)
        lines.append(
            f"  ok = runtime.register_type(kTypeId{ident}, kTypeHash{ident}) && ok;"
        )
    lines += ["  return ok;", "}", ""]
    lines.append(f"constexpr size_t kWasmPreciseAllocationSiteCount = {precise_count};")
    lines.append(
        f"constexpr size_t kWasmHelperAllocationSiteCount = {len(records) - precise_count};"
    )
    lines.append(f"constexpr size_t kWasmAllocationSiteCount = {len(records)};")
    if records:
        lines += ["constexpr WasmAllocationSitePolicy kWasmAllocationSites[] = {"]
        for record in records:
            type_ident = cpp(record["type"])
            helper_value = "true" if record["helper"] else "false"
            lines.append(
                f'  {{{record["site_id"]}, kTypeId{type_ident}, '
                f'"{record["import_name"]}", {helper_value}}},'
            )
        lines += ["};", ""]
    lines += [
        "inline bool register_wasm_allocation_policy(Runtime& runtime)",
        "{",
    ]
    if records:
        lines += [
            "  for (const auto& site : kWasmAllocationSites) {",
            "    if (!runtime.register_allocation_site_id(site.site_id, site.type_id))",
            "      return false;",
            "  }",
        ]
    lines += ["  return true;", "}", ""]

    for use in policy["uses"]:
        if use["type"] not in ids:
            raise ValueError(f"unknown use type: {use['type']}")
        use_ident = cpp(use["name"])
        type_ident = cpp(use["type"])
        offset = int(use["offset"])
        dynamic = bool(use.get("dynamic_bytes"))
        size = 0 if dynamic else int(use.get("bytes", 0))
        if offset < 0 or size < 0:
            raise ValueError(f"negative access range: {use['name']}")
        lines += [
            f"constexpr AccessPolicy kUse{use_ident}{{",
            f"  kTypeHash{type_ident}, {offset}, {size}}};",
        ]

    lines += [
        "",
        "inline CheckResult check(const Runtime& runtime, uintptr_t base,",
        "                         size_t dynamic_bytes, AccessPolicy policy)",
        "{",
        "  const size_t bytes = policy.bytes ? policy.bytes : dynamic_bytes;",
        "  if (policy.offset > std::numeric_limits<size_t>::max() - bytes)",
        "    return CheckResult::out_of_bounds;",
        "  return runtime.check(base, policy.offset + bytes, policy.type_hash);",
        "}",
        "",
        f"}}  // namespace {namespace_name}",
        "",
    ]
    return "\n".join(lines)


def generate_host_imports(records):
    lines = [
        '#include "wasm2c_rt_mem.h"',
        "",
        "#include <stdint.h>",
        "",
    ]
    for record in records:
        lines += [
            f"uint32_t w2c_env_{record['import_name']}(struct w2c_env* env, uint32_t size)",
            "{",
            "  if (!env || !env->interspec_allocate) return 0;",
            f"  return env->interspec_allocate(env->interspec_context, UINT32_C({record['site_id']}), size);",
            "}",
            "",
        ]
    lines += [
        "uint32_t w2c_env_interspecWasmRelease(struct w2c_env* env, uint32_t ptr)",
        "{",
        "  if (!env || !env->interspec_release) return 0;",
        "  return env->interspec_release(env->interspec_context, ptr);",
        "}",
        "",
        "uint32_t w2c_env_interspecWasmSize(struct w2c_env* env, uint32_t ptr)",
        "{",
        "  if (!env || !env->interspec_size) return 0;",
        "  return env->interspec_size(env->interspec_context, ptr);",
        "}",
        "",
        "uint32_t w2c_env_interspecWasmReallocate(struct w2c_env* env, uint32_t ptr, uint32_t size)",
        "{",
        "  if (!env || !env->interspec_reallocate) return 0;",
        "  return env->interspec_reallocate(env->interspec_context, ptr, size);",
        "}",
        "",
    ]
    return "\n".join(lines)


def generate_wasm_boundary(policy, source, namespace_name, boundary=None):
    policy = prepare_policy(policy, boundary)
    known_types = set(policy["types"])
    for allocation in policy["allocations"]:
        if allocation["type"] not in known_types:
            raise ValueError(f"unknown allocation type: {allocation['type']}")
    for helper in (boundary or {}).get("helper_sites", []):
        if helper["type"] not in known_types:
            raise ValueError(f"unknown helper site type: {helper['type']}")

    records, precise_count = site_records(policy, boundary, namespace_name)
    precise = list(enumerate(policy["allocations"], start=1))
    precise.sort(
        key=lambda entry: (
            int(entry[1]["site"]["start_line"]),
            int(entry[1]["site"]["start_column"]),
        ),
        reverse=True,
    )
    instrumented = source
    for site_id, allocation in precise:
        instrumented = instrument_site(
            instrumented, allocation, site_id, namespace_name
        )

    return (
        instrumented,
        generate_u_header(policy["types"], records),
        generate_t_header(policy, records, precise_count, namespace_name),
        generate_host_imports(records),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--namespace", default="interspec::generated")
    parser.add_argument("--boundary")
    args = parser.parse_args()

    policy = json.loads(Path(args.policy).read_text())
    boundary = json.loads(Path(args.boundary).read_text()) if args.boundary else None
    source_path = Path(args.source)
    instrumented, u_header, t_header, host_imports = generate_wasm_boundary(
        policy, source_path.read_text(), args.namespace, boundary
    )
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / source_path.name).write_text(instrumented)
    (out / "interspec_u_policy.h").write_text(u_header)
    (out / "interspec_t_policy.h").write_text(t_header)
    (out / "interspec_wasm_imports.c").write_text(host_imports)


if __name__ == "__main__":
    main()
