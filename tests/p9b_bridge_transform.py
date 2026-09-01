#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_p9b_wasm2c_bridge import transform


def main():
    source = (ROOT / "integration/rsync_popt/p4c_bridge.cpp").read_text()
    result = transform(source)
    assert "rlbox_wasm2c_sandbox.hpp" in result
    assert "RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c" in result
    assert "rlbox_nacl_sandbox" not in result
    assert "create_sandbox()" in result
    assert "reserve_typed_arena" in result
    assert "register_wasm_allocation_policy" in result
    assert "set_interspec_runtime" in result
    assert "allocate_for_site" in result
    assert "p9b_allocate" in result
    assert "callback_slot_for_key" not in result
    assert "register_callback(p4c_allocate)" not in result
    assert "interspec_popt_init_lifetime" not in result
    assert "callback_program_counter" not in result
    assert "sandbox_address(raw)" in result
    print("InterSpec P9b wasm2c bridge transform: all checks passed")


if __name__ == "__main__":
    main()
