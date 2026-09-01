#!/usr/bin/env python3

import argparse
import re
from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise ValueError(f"expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


def regex_once(text, pattern, replacement, label, flags=0):
    result, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise ValueError(f"expected exactly one {label}, found {count}")
    return result


def transform(text):
    text = replace_once(
        text,
        '#include "rlbox.hpp"\n#include "rlbox_nacl_sandbox.hpp"',
        '#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol\n'
        '#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c\n'
        '#include "glue_lib_wasm2c.h"\n'
        '#include "rlbox.hpp"\n'
        '#include "rlbox_wasm2c_sandbox.hpp"',
        "sandbox headers",
    )
    text = replace_once(
        text,
        "using SandboxType = rlbox::rlbox_nacl_sandbox;",
        "using SandboxType = rlbox::rlbox_wasm2c_sandbox;",
        "sandbox type",
    )
    text = regex_once(
        text,
        r"using p4c_release_fn =.*?using p4c_realloc_fn = uint32_t \(\*\)\(uint32_t, uint32_t\);\n\n",
        "",
        "NaCl lifetime typedefs",
        flags=re.S,
    )
    text = regex_once(
        text,
        r"void interspec_popt_init_lifetime\(uint32_t,\n\s+p4c_release_fn,\n\s+p4c_size_fn,\n\s+p4c_realloc_fn\);\n",
        "",
        "NaCl lifetime declaration",
    )
    text = regex_once(
        text,
        r"class Engine;\nEngine& engine_from\(Sandbox& sandbox\);\n\nstatic U32 p4c_allocate.*?static U32 p4c_reallocate\(Sandbox& sandbox, U32 ptr, U32 size\);\n",
        "class Engine;\n"
        "static uint32_t p9b_allocate(void*, uint32_t, uint32_t);\n"
        "static uint32_t p9b_release(void*, uint32_t);\n"
        "static uint32_t p9b_size(void*, uint32_t);\n"
        "static uint32_t p9b_reallocate(void*, uint32_t, uint32_t);\n",
        "NaCl callback declarations",
        flags=re.S,
    )

    constructor = '''  Engine() {
    if (!sandbox_.create_sandbox())
      throw std::runtime_error("failed to create RLBox wasm2c sandbox");

    constexpr uint32_t kArenaSize = 16u * 1024u * 1024u;
    const uint32_t arena_base =
      sandbox_.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
    if (!arena_base) throw std::runtime_error("failed to reserve typed arena");

    policy_runtime_ =
      std::make_unique<interspec::PolicyRuntime>(arena_base, kArenaSize);
    auto& runtime = policy_runtime_->runtime();
    if (!interspec::rsync_popt_generated::register_types(runtime) ||
        !interspec::rsync_popt_generated::register_wasm_allocation_policy(runtime))
      throw std::runtime_error("failed to initialize wasm InterSpec allocation policy");

    sandbox_.sandbox_storage = this;
    sandbox_.get_sandbox_impl()->set_interspec_runtime(
      this, p9b_allocate, p9b_release, p9b_size, p9b_reallocate);
  }
'''
    text = regex_once(
        text,
        r"  Engine\(\) \{.*?\n  \}\n\n  Sandbox& sandbox\(\)",
        constructor + "\n  Sandbox& sandbox()",
        "Engine constructor",
        flags=re.S,
    )
    text = regex_once(
        text,
        r"  uintptr_t allocate_for_callback_pc\(uint32_t size\) \{.*?\n  \}\n",
        "  uintptr_t allocate_for_site(uint32_t site_id, uint32_t size) {\n"
        "    return runtime().allocate_from_site(size, site_id);\n"
        "  }\n",
        "allocation dispatch method",
        flags=re.S,
    )
    text = regex_once(
        text,
        r" private:\n  using AllocCallback =.*?  ReallocCallback realloc_cb_;\n",
        " private:\n  Sandbox sandbox_;\n"
        "  std::unique_ptr<interspec::PolicyRuntime> policy_runtime_;\n",
        "NaCl callback members",
        flags=re.S,
    )
    # The replacement above includes sandbox/runtime, so remove their original
    # duplicate declarations if the source layout kept them before callback fields.
    text = text.replace(
        "  Sandbox sandbox_;\n  std::unique_ptr<interspec::PolicyRuntime> policy_runtime_;\n"
        "  Sandbox sandbox_;\n  std::unique_ptr<interspec::PolicyRuntime> policy_runtime_;\n",
        "  Sandbox sandbox_;\n  std::unique_ptr<interspec::PolicyRuntime> policy_runtime_;\n",
    )

    host_dispatch = '''static uint32_t p9b_allocate(void* context, uint32_t site_id, uint32_t size) {
  auto* value = static_cast<Engine*>(context);
  return value ? static_cast<uint32_t>(value->allocate_for_site(site_id, size)) : 0u;
}

static uint32_t p9b_release(void* context, uint32_t ptr) {
  auto* value = static_cast<Engine*>(context);
  return value && value->runtime().release(ptr) ? 1u : 0u;
}

static uint32_t p9b_size(void* context, uint32_t ptr) {
  auto* value = static_cast<Engine*>(context);
  if (!value) return 0u;
  size_t size = 0;
  if (!value->runtime().allocation_size(ptr, size) ||
      size > std::numeric_limits<uint32_t>::max())
    return 0u;
  return static_cast<uint32_t>(size);
}

static uint32_t p9b_reallocate(void* context, uint32_t ptr, uint32_t size) {
  auto* value = static_cast<Engine*>(context);
  return value ? static_cast<uint32_t>(value->runtime().reallocate(ptr, size)) : 0u;
}

'''
    text = regex_once(
        text,
        r"Engine& engine_from\(Sandbox& sandbox\) \{.*?\n\}\n\nstatic U32 p4c_allocate.*?\n\}\n\nenum class SlotKind",
        host_dispatch + "enum class SlotKind",
        "NaCl callback implementations",
        flags=re.S,
    )
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(transform(Path(args.source).read_text()))


if __name__ == "__main__":
    main()
