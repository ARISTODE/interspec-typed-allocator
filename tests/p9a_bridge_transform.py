#!/usr/bin/env python3

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_p9a_rlbox_only_bridge import transform


def main():
    source = (ROOT / "integration/rsync_popt/p4c_bridge.cpp").read_text()
    generated = transform(source)
    assert "reserve_typed_arena" not in generated
    assert "initialize_from_sandbox" not in generated
    assert "register_callback(p4c_allocate)" not in generated
    assert "invoke_sandbox_function(interspec_p4c_typed_copy, temporary)" not in generated
    assert "RLBox-only marshalling uses the sandbox's ordinary allocator" in generated
    assert "#ifdef INTERSPEC_P9A_RLBOX_ONLY" in generated
    assert "#elif defined(INTERSPEC_P8_MEASURE_NO_VALIDATION)" in generated
    print("P9a RLBox-only bridge transform tests: ok")


if __name__ == "__main__":
    main()
