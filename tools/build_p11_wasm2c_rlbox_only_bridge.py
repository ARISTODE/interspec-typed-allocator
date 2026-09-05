#!/usr/bin/env python3

import argparse
import re
from pathlib import Path


def regex_once(text, pattern, replacement, label, flags=0):
    result, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise ValueError(f"expected exactly one {label}, found {count}")
    return result


RLBOX_ONLY_CONSTRUCTOR = '''  Engine() {
    if (!sandbox_.create_sandbox())
      throw std::runtime_error("failed to create RLBox wasm2c sandbox");

    /*
     * P11 RLBox-only runtime-path baseline. Do not reserve the InterSpec typed
     * arena, instantiate PolicyRuntime, register allocation-site provenance,
     * or install InterSpec allocation/lifetime callbacks.
     */
    sandbox_.sandbox_storage = this;
  }
'''

RLBOX_ONLY_COPY_TO_U = '''  UCharPtr copy_to_u(const char* src) {
    if (!src) return UCharPtr(nullptr);

    const size_t bytes = std::strlen(src) + 1;
    if (bytes > std::numeric_limits<uint32_t>::max())
      throw std::runtime_error("popt string exceeds sandbox ABI");

    /* P11 RLBox-only marshalling uses the ordinary sandbox allocator. */
    auto copy = sandbox_.malloc_in_sandbox<char>(static_cast<uint32_t>(bytes));
    if (copy.UNSAFE_unverified() == nullptr) throw std::bad_alloc();
    std::memcpy(copy.UNSAFE_unverified(), src, bytes);
    return copy;
  }
'''


def transform(text):
    text = regex_once(
        text,
        r"  Engine\(\) \{.*?\n  \}\n\n  Sandbox& sandbox\(\)",
        RLBOX_ONLY_CONSTRUCTOR + "\n  Sandbox& sandbox()",
        "wasm Engine constructor",
        flags=re.S,
    )
    text = regex_once(
        text,
        r"  UCharPtr copy_to_u\(const char\* src\) \{.*?\n  \}\n\n  char\* copy_checked",
        RLBOX_ONLY_COPY_TO_U + "\n  char* copy_checked",
        "copy_to_u",
        flags=re.S,
    )

    forbidden = (
        "reserve_typed_arena",
        "set_interspec_runtime",
        "register_wasm_allocation_policy",
    )
    for marker in forbidden:
        if marker in text:
            raise ValueError(f"RLBox-only bridge still contains active setup marker: {marker}")

    call = "sandbox_.invoke_sandbox_function(interspec_p4c_typed_copy"
    if call in text:
        raise ValueError("RLBox-only copy_to_u still uses the typed-copy path")
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(transform(Path(args.source).read_text()))


if __name__ == "__main__":
    main()
