#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_p9b_wasm2c_bridge import transform as to_wasm2c
from tools.build_p11_wasm2c_rlbox_only_bridge import transform as to_rlbox_only


def main():
    source = (ROOT / "integration/rsync_popt/p4c_bridge.cpp").read_text()
    wasm = to_wasm2c(source)
    baseline = to_rlbox_only(wasm)

    assert "rlbox_wasm2c_sandbox" in baseline
    assert "failed to create RLBox wasm2c sandbox" in baseline
    assert "reserve_typed_arena" not in baseline
    assert "set_interspec_runtime" not in baseline
    assert "register_wasm_allocation_policy" not in baseline
    assert "sandbox_.malloc_in_sandbox<char>" in baseline
    assert "sandbox_.invoke_sandbox_function(interspec_p4c_typed_copy" not in baseline
    assert "#ifdef INTERSPEC_P8_MEASURE_NO_VALIDATION" in baseline
    assert "P11 RLBox-only runtime-path baseline" in baseline

    print("InterSpec P11 wasm2c RLBox-only bridge transform: all checks passed")


if __name__ == "__main__":
    main()
