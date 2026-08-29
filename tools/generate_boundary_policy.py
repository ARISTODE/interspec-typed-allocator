#!/usr/bin/env python3

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.generate_policy import cpp, exported_label_asm, generate, macro, symbol


def helper_symbols(namespace_name, name, site_id):
    # Helper labels are process-global ELF symbols even though their T policy is
    # emitted in a C++ namespace. P7c compiles multiple generated boundaries
    # into one NaCl module, so helper name + local SiteId is not globally unique.
    # Fold the generated boundary namespace into the ELF label while keeping the
    # U-facing helper macro local and readable.
    prefix = (
        f"interspec_alloc_site_{symbol(namespace_name)}_"
        f"{symbol(name)}_{site_id}"
    )
    return prefix + "_begin", prefix + "_end"


def helper_macro(name, suffix):
    return f"INTERSPEC_SITE_{macro(name)}_{suffix}"


def inject_before_namespace_close(header, namespace_name, lines):
    marker = f"}}  // namespace {namespace_name}"
    pos = header.rfind(marker)
    if pos < 0:
        raise ValueError(f"generated namespace close not found: {namespace_name}")
    prefix = header[:pos].rstrip() + "\n\n"
    suffix = header[pos:]
    return prefix + "\n".join(lines).rstrip() + "\n\n" + suffix


def prepare_policy(policy, boundary):
    composed = copy.deepcopy(policy)
    boundary = boundary or {}
    extra_types = boundary.get("types", [])
    if not isinstance(extra_types, list):
        raise ValueError("boundary types must be a list")
    known_types = set(composed["types"])
    for type_name in extra_types:
        if not isinstance(type_name, str) or not type_name:
            raise ValueError("boundary type names must be non-empty strings")
        if type_name not in known_types:
            composed["types"].append(type_name)
            known_types.add(type_name)
    dynamic_uses = []
    for use in composed["uses"]:
        if use.get("dynamic_bytes"):
            if "bytes" in use and int(use["bytes"]) != 0:
                raise ValueError(
                    f"dynamic use must not also declare fixed bytes: {use['name']}"
                )
            use["bytes"] = 0
            dynamic_uses.append(use["name"])
    return composed, dynamic_uses


def generate_boundary(policy, source, namespace_name="interspec::generated",
                      boundary=None):
    boundary = boundary or {}
    helpers = boundary.get("helper_sites", [])
    policy, dynamic_uses = prepare_policy(policy, boundary)
    instrumented, u_header, t_header = generate(policy, source)

    default_namespace = "interspec::generated"
    if namespace_name != default_namespace:
        t_header = t_header.replace(
            f"namespace {default_namespace}", f"namespace {namespace_name}")
        t_header = t_header.replace(
            f"}}  // namespace {default_namespace}",
            f"}}  // namespace {namespace_name}")

    known_types = set(policy["types"])
    precise_count = sum(1 for allocation in policy["allocations"] if "site" in allocation)
    seen_names = set()
    helper_entries = []
    u_lines = []
    for index, helper in enumerate(helpers, start=1):
        name = helper["name"]
        type_name = helper["type"]
        if name in seen_names:
            raise ValueError(f"duplicate helper site: {name}")
        if type_name not in known_types:
            raise ValueError(f"unknown helper site type: {type_name}")
        seen_names.add(name)
        site_id = precise_count + index
        begin_symbol, end_symbol = helper_symbols(namespace_name, name, site_id)
        type_ident = cpp(type_name)
        helper_entries.append((site_id, type_ident, begin_symbol, end_symbol))
        begin_asm = exported_label_asm(begin_symbol)
        end_asm = exported_label_asm(end_symbol)
        u_lines += [
            f"#define {helper_macro(name, 'BEGIN')}() \\",
            f"  __asm__ __volatile__(\"{begin_asm}\" ::: \"memory\")",
            f"#define {helper_macro(name, 'END')}() \\",
            f"  __asm__ __volatile__(\"{end_asm}\" ::: \"memory\")",
            "",
        ]

    if u_lines:
        u_header = u_header.rstrip() + "\n\n" + "\n".join(u_lines).rstrip() + "\n"

    t_lines = [
        "struct HelperAllocationSitePolicy {",
        "  SiteId site_id;",
        "  TypeId type_id;",
        "  const char* begin_symbol;",
        "  const char* end_symbol;",
        "};",
        "",
        f"constexpr size_t kHelperAllocationSiteCount = {len(helper_entries)};",
    ]
    if helper_entries:
        t_lines += ["constexpr HelperAllocationSitePolicy kHelperAllocationSites[] = {"]
        for site_id, type_ident, begin_symbol, end_symbol in helper_entries:
            t_lines.append(
                f'  {{{site_id}, kTypeId{type_ident}, "{begin_symbol}", "{end_symbol}"}},'
            )
        t_lines += ["};", "", "template<typename Resolver>",
                    "inline bool register_helper_allocation_sites(Runtime& runtime, Resolver resolve)",
                    "{", "  for (const auto& site : kHelperAllocationSites) {",
                    "    const uintptr_t begin = resolve(site.begin_symbol);",
                    "    const uintptr_t end = resolve(site.end_symbol);",
                    "    if (!begin || !end ||",
                    "        !runtime.register_allocation_site(site.site_id, begin, end, site.type_id))",
                    "      return false;", "  }", "  return true;", "}", ""]
    else:
        t_lines += ["template<typename Resolver>",
                    "inline bool register_helper_allocation_sites(Runtime&, Resolver)",
                    "{", "  return true;", "}", ""]

    t_lines += [
        "constexpr size_t kTotalAllocationSiteCount =",
        "    kAllocationSiteCount + kHelperAllocationSiteCount;",
        "",
        "template<typename Resolver>",
        "inline bool register_allocation_policy(Runtime& runtime, Resolver resolve)",
        "{",
        "  if (!register_allocation_sites(runtime, resolve)) return false;",
        "  return register_helper_allocation_sites(runtime, resolve);",
        "}",
    ]

    if dynamic_uses:
        t_lines += [
            "", "inline CheckedAccess checked_dynamic_access(const Runtime& runtime,",
            "                                            uintptr_t base,",
            "                                            size_t dynamic_bytes,",
            "                                            AccessPolicy policy)", "{",
            "  if (policy.bytes != 0 ||",
            "      policy.offset > std::numeric_limits<size_t>::max() - dynamic_bytes)",
            "    return {CheckResult::out_of_bounds, 0, 0};",
            "  const size_t extent = policy.offset + dynamic_bytes;",
            "  const CheckResult result = runtime.check(base, extent, policy.type_hash);",
            "  if (result != CheckResult::ok) return {result, 0, 0};",
            "  return {result, base + policy.offset, dynamic_bytes};", "}", "",
            "inline CheckResult check_dynamic(const Runtime& runtime,",
            "                                 uintptr_t base,",
            "                                 size_t dynamic_bytes,",
            "                                 AccessPolicy policy)", "{",
            "  return checked_dynamic_access(runtime, base, dynamic_bytes, policy).result;",
            "}", "", f"constexpr size_t kDynamicUseCount = {len(dynamic_uses)};",
        ]

    t_header = inject_before_namespace_close(t_header, namespace_name, t_lines)
    return instrumented, u_header, t_header


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
    instrumented, u_header, t_header = generate_boundary(
        policy, source_path.read_text(), args.namespace, boundary)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / source_path.name).write_text(instrumented)
    (out / "interspec_u_policy.h").write_text(u_header)
    (out / "interspec_t_policy.h").write_text(t_header)


if __name__ == "__main__":
    main()
