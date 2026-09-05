#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.generate_wasm_boundary_policy import generate_wasm_boundary


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
  return malloc(n + 1);
}
"""
    policy = {
        "types": ["char"],
        "allocations": [{
            "function": "make_value",
            "type": "char",
            "site": span(source, "malloc(n + 1)"),
        }],
        "uses": [{"name": "first_byte", "type": "char", "offset": 0, "bytes": 1}],
    }
    boundary = {
        "helper_sites": [{"name": "typed_copy", "type": "char"}]
    }
    namespace = "interspec::sample_generated"
    instrumented, u_header, t_header, imports = generate_wasm_boundary(
        policy, source, namespace, boundary
    )

    assert "malloc(n + 1)" not in instrumented
    assert "interspec_wasm_alloc_interspec__sample_generated_site_1" in instrumented
    assert "INTERSPEC_SITE_ALLOC" not in instrumented
    assert "__asm__" not in instrumented
    assert "import_module(\"env\")" not in u_header
    assert 'INTERSPEC_WASM_IMPORT("env", "interspecWasmAllocInterspecSampleGeneratedSite1")' in u_header
    assert 'INTERSPEC_WASM_IMPORT("env", "interspecWasmAllocInterspecSampleGeneratedSite2")' in u_header
    assert "INTERSPEC_SITE_TYPED_COPY_ALLOC" in u_header
    assert "interspecWasmRelease" in u_header
    assert "kWasmSiteIdBase = UINT32_C(0)" in t_header
    assert "kWasmPreciseAllocationSiteCount = 1" in t_header
    assert "kWasmHelperAllocationSiteCount = 1" in t_header
    assert "register_allocation_site_id" in t_header
    assert "register_wasm_allocation_policy" in t_header
    assert "w2c_env_interspecWasmAllocInterspecSampleGeneratedSite1" in imports
    assert "UINT32_C(1), size" in imports
    assert "w2c_env_interspecWasmAllocInterspecSampleGeneratedSite2" in imports
    assert "UINT32_C(2), size" in imports
    assert "w2c_env_interspecWasmReallocate" in imports
    assert "site_id" not in instrumented

    # Multi-policy Wasm modules give each generated policy a trusted numeric
    # namespace. Import names remain source-site local while runtime SiteIds are
    # disjoint, so reaching an import from a foreign policy cannot be replayed
    # as an authorized site in the active PolicyRuntime.
    _, namespaced_u, namespaced_t, namespaced_imports = generate_wasm_boundary(
        policy, source, namespace, boundary, site_id_base=0x10000
    )
    assert namespaced_u == u_header
    assert "kWasmSiteIdBase = UINT32_C(65536)" in namespaced_t
    assert "{65537, kTypeIdChar" in namespaced_t
    assert "{65538, kTypeIdChar" in namespaced_t
    assert "UINT32_C(65537), size" in namespaced_imports
    assert "UINT32_C(65538), size" in namespaced_imports
    assert "interspecWasmAllocInterspecSampleGeneratedSite1" in namespaced_imports
    assert "interspecWasmAllocInterspecSampleGeneratedSite2" in namespaced_imports

    try:
        generate_wasm_boundary(
            policy, source, namespace, boundary, site_id_base=0xFFFFFFFF
        )
        raise AssertionError("overflowing site-id namespace should be rejected")
    except ValueError as error:
        assert "overflows uint32_t" in str(error)

    try:
        bad = dict(policy)
        bad["allocations"] = [{"function": "make_value", "type": "char"}]
        generate_wasm_boundary(bad, source, namespace)
        raise AssertionError("legacy allocation should be rejected")
    except ValueError as error:
        assert "precise source allocation site" in str(error)

    print("InterSpec P9b wasm-direct policy codegen: all checks passed")


if __name__ == "__main__":
    main()
