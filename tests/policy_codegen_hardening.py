#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.generate_policy import generate


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
void* choose(size_t n) {
  void* first = malloc(n + 7);
  void* second = malloc((n * 2) + 1);
  return second ? second : first;
}
"""

    selected = "malloc((n * 2) + 1)"
    policy = {
        "types": ["char"],
        "allocations": [
            {
                "function": "choose",
                "type": "char",
                "site": span(source, selected),
            }
        ],
        "uses": [
            {"name": "byte", "type": "char", "offset": 0, "bytes": 1}
        ],
    }

    instrumented, u_header, t_header = generate(policy, source)
    assert "malloc(n + 7)" in instrumented
    assert selected not in instrumented
    assert "INTERSPEC_SITE_ALLOC(__interspec_size)" in instrumented
    assert "interspec_alloc_site_choose_1_begin" in instrumented
    assert "interspec_alloc_site_choose_1_end" in instrumented
    assert "interspec_site_allocator.h" in u_header
    assert "INTERSPEC_TYPE_ID_CHAR" in u_header
    assert "AllocationSitePolicy" in t_header
    assert "kAllocationSiteCount = 1" in t_header
    assert '"interspec_alloc_site_choose_1_begin"' in t_header
    assert '"interspec_alloc_site_choose_1_end"' in t_header
    assert "register_allocation_sites" in t_header
    assert "runtime.register_allocation_site" in t_header
    assert "std::numeric_limits<size_t>::max() - policy.bytes" in t_header

    print("InterSpec policy codegen hardening: all checks passed")


if __name__ == "__main__":
    main()
