#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.generate_policy import cpp, exported_label_asm, generate, macro, symbol


def helper_symbols(name, site_id):
    prefix = f"interspec_alloc_site_{symbol(name)}_{site_id}"
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


def generate_boundary(policy, source, namespace_name="interspec::generated",
                      boundary=None):
    boundary = boundary or {}
    helpers = boundary.get("helper_sites", [])

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
        begin_symbol, end_symbol = helper_symbols(name, site_id)
        type_ident = cpp(type_name)
        helper_entries.append((site_id, type_ident, begin_symbol, end_symbol))

        # exported_label_asm() already returns text escaped for a C string
        # literal (for example, "...\\n.type ...").  Escaping it a second time
        # would emit literal backslashes to the assembler rather than line
        # separators, which the NaCl assembler correctly rejects.
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
        t_lines += ["};", ""]
        t_lines += [
            "template<typename Resolver>",
            "inline bool register_helper_allocation_sites(Runtime& runtime, Resolver resolve)",
            "{",
            "  for (const auto& site : kHelperAllocationSites) {",
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
        t_lines += [
            "template<typename Resolver>",
            "inline bool register_helper_allocation_sites(Runtime&, Resolver)",
            "{",
            "  return true;",
            "}",
            "",
        ]

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
    source = source_path.read_text()

    instrumented, u_header, t_header = generate_boundary(
        policy, source, args.namespace, boundary)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / source_path.name).write_text(instrumented)
    (out / "interspec_u_policy.h").write_text(u_header)
    (out / "interspec_t_policy.h").write_text(t_header)


if __name__ == "__main__":
    main()
