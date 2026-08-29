#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.generate_boundary_policy import generate_boundary


def span(source, needle):
    start = source.index(needle)
    end = start + len(needle) - 1

    def location(offset):
        line = source.count("\n", 0, offset) + 1
        line_start = source.rfind("\n", 0, offset) + 1
        return line, offset - line_start + 1

    start_line, start_column = location(start)
    end_line, end_column = location(end)
    return {
        "start_line": start_line,
        "start_column": start_column,
        "end_line": end_line,
        "end_column": end_column,
    }


def main():
    source = """#include <stdlib.h>
void* make_value(size_t n) {
  return malloc(n);
}
"""
    policy = {
        "types": ["char"],
        "allocations": [
            {
                "function": "make_value",
                "type": "char",
                "site": span(source, "malloc(n)"),
            }
        ],
        "uses": [
            {"name": "first_byte", "type": "char", "offset": 0, "bytes": 1}
        ],
    }
    boundary = {
        "helper_sites": [
            {"name": "typed_copy", "type": "char"},
        ]
    }

    instrumented, u_header, t_header = generate_boundary(
        policy,
        source,
        namespace_name="interspec::sample_generated",
        boundary=boundary,
    )

    assert "INTERSPEC_SITE_ALLOC(__interspec_size)" in instrumented
    assert "namespace interspec::sample_generated" in t_header
    assert "namespace interspec::generated" not in t_header

    assert "INTERSPEC_SITE_TYPED_COPY_BEGIN" in u_header
    assert "INTERSPEC_SITE_TYPED_COPY_END" in u_header
    assert "interspec_alloc_site_typed_copy_2_begin" in u_header
    assert "interspec_alloc_site_typed_copy_2_end" in u_header

    # Helper labels must contain one C-string newline escape.  A previous P7b
    # implementation escaped exported_label_asm() twice, producing literal
    # backslashes in the emitted assembly and failing the NaCl assembler.
    expected_begin_asm = (
        ".globl interspec_alloc_site_typed_copy_2_begin\\n"
        ".type interspec_alloc_site_typed_copy_2_begin,@function\\n"
        "interspec_alloc_site_typed_copy_2_begin:"
    )
    expected_end_asm = (
        ".globl interspec_alloc_site_typed_copy_2_end\\n"
        ".type interspec_alloc_site_typed_copy_2_end,@function\\n"
        "interspec_alloc_site_typed_copy_2_end:"
    )
    assert expected_begin_asm in u_header
    assert expected_end_asm in u_header
    assert "typed_copy_2_begin\\\\n.type" not in u_header
    assert "typed_copy_2_end\\\\n.type" not in u_header

    assert "kAllocationSiteCount = 1" in t_header
    assert "kHelperAllocationSiteCount = 1" in t_header
    assert "kTotalAllocationSiteCount" in t_header
    assert '"interspec_alloc_site_typed_copy_2_begin"' in t_header
    assert '"interspec_alloc_site_typed_copy_2_end"' in t_header
    assert "register_allocation_policy" in t_header
    assert "register_helper_allocation_sites" in t_header

    try:
        generate_boundary(
            policy,
            source,
            boundary={"helper_sites": [{"name": "bad", "type": "unknown"}]},
        )
        raise AssertionError("unknown helper type should fail")
    except ValueError as error:
        assert "unknown helper site type" in str(error)

    print("InterSpec boundary policy codegen: all checks passed")


if __name__ == "__main__":
    main()
