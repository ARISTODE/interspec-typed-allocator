#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.generate_boundary_policy import generate_boundary
from tools.generate_policy import symbol


def span(source, needle):
    start = source.index(needle)
    end = start + len(needle) - 1
    def location(offset):
        line = source.count("\n", 0, offset) + 1
        line_start = source.rfind("\n", 0, offset) + 1
        return line, offset - line_start + 1
    start_line, start_column = location(start)
    end_line, end_column = location(end)
    return {"start_line": start_line, "start_column": start_column,
            "end_line": end_line, "end_column": end_column}


def prefix_for(namespace, helper, site_id):
    return f"interspec_alloc_site_{symbol(namespace)}_{symbol(helper)}_{site_id}"


def main():
    source = """#include <stdlib.h>
void* make_value(size_t n) {
  return malloc(n);
}
"""
    policy = {
        "types": ["char"],
        "allocations": [{"function": "make_value", "type": "char",
                         "site": span(source, "malloc(n)")}],
        "uses": [
            {"name": "first_byte", "type": "char", "offset": 0, "bytes": 1},
            {"name": "runtime_range", "type": "char", "offset": 0,
             "dynamic_bytes": True},
        ],
    }
    boundary = {"types": ["byte_copy"],
                "helper_sites": [{"name": "typed_copy", "type": "byte_copy"}]}
    namespace = "interspec::sample_generated"
    instrumented, u_header, t_header = generate_boundary(
        policy, source, namespace_name=namespace, boundary=boundary)

    assert "INTERSPEC_SITE_ALLOC(__interspec_size)" in instrumented
    assert f"namespace {namespace}" in t_header
    assert "namespace interspec::generated" not in t_header
    assert "INTERSPEC_SITE_TYPED_COPY_BEGIN" in u_header
    assert "INTERSPEC_SITE_TYPED_COPY_END" in u_header

    prefix = prefix_for(namespace, "typed_copy", 2)
    assert prefix + "_begin" in u_header
    assert prefix + "_end" in u_header
    expected_begin_asm = (
        f".globl {prefix}_begin\\n"
        f".type {prefix}_begin,@function\\n"
        f"{prefix}_begin:"
    )
    expected_end_asm = (
        f".globl {prefix}_end\\n"
        f".type {prefix}_end,@function\\n"
        f"{prefix}_end:"
    )
    assert expected_begin_asm in u_header
    assert expected_end_asm in u_header
    assert "typed_copy_2_begin\\\\n.type" not in u_header
    assert "typed_copy_2_end\\\\n.type" not in u_header

    assert "kTypeIdByteCopy" in t_header
    assert "kAllocationSiteCount = 1" in t_header
    assert "kHelperAllocationSiteCount = 1" in t_header
    assert "kTotalAllocationSiteCount" in t_header
    assert f'"{prefix}_begin"' in t_header
    assert f'"{prefix}_end"' in t_header
    assert "register_allocation_policy" in t_header
    assert "register_helper_allocation_sites" in t_header
    assert "kUseRuntimeRange" in t_header
    assert "checked_dynamic_access" in t_header
    assert "check_dynamic" in t_header
    assert "kDynamicUseCount = 1" in t_header
    assert "policy.offset > std::numeric_limits<size_t>::max() - dynamic_bytes" in t_header

    other_namespace = "interspec::other_generated"
    _, u_other, t_other = generate_boundary(
        policy, source, namespace_name=other_namespace, boundary=boundary)
    other_prefix = prefix_for(other_namespace, "typed_copy", 2)
    assert other_prefix + "_begin" in u_other
    assert prefix + "_begin" not in u_other
    assert f'"{other_prefix}_begin"' in t_other

    try:
        generate_boundary(policy, source,
                          boundary={"helper_sites": [{"name": "bad", "type": "unknown"}]})
        raise AssertionError("unknown helper type should fail")
    except ValueError as error:
        assert "unknown helper site type" in str(error)

    try:
        bad_policy = dict(policy)
        bad_policy["uses"] = [{"name": "bad_dynamic", "type": "char", "offset": 0,
                               "bytes": 4, "dynamic_bytes": True}]
        generate_boundary(bad_policy, source)
        raise AssertionError("dynamic use with fixed bytes should fail")
    except ValueError as error:
        assert "dynamic use must not also declare fixed bytes" in str(error)

    print("InterSpec boundary policy codegen: all checks passed")


if __name__ == "__main__":
    main()
