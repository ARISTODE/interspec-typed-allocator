#!/usr/bin/env python3

import argparse
import json
import subprocess
from pathlib import Path


def replace(path, old, new):
    text = path.read_text()
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"backend patch context not found in {path}")
    path.write_text(text.replace(old, new, 1))


def require_head(repo, expected):
    actual = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != expected:
        raise RuntimeError(
            f"unsupported checkout at {repo}: expected {expected}, got {actual}"
        )


def apply_backend(root):
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / "manifest.json").read_text())
    require_head(root, manifest["rlbox_wasm2c_sandbox"]["commit"])

    cmake = root / "CMakeLists.txt"
    replace(
        cmake,
        "FetchContent_Declare(\n  rlbox\n  GIT_REPOSITORY https://github.com/PLSysSec/rlbox.git\n  GIT_TAG main)",
        "FetchContent_Declare(\n  rlbox\n  GIT_REPOSITORY https://github.com/PLSysSec/rlbox.git\n  GIT_TAG "
        + manifest["rlbox"]["commit"]
        + ")",
    )
    replace(
        cmake,
        "FetchContent_Declare(\n  wasm2c_compiler\n  GIT_REPOSITORY https://github.com/WebAssembly/wabt/\n  GIT_TAG main)",
        "FetchContent_Declare(\n  wasm2c_compiler\n  GIT_REPOSITORY https://github.com/WebAssembly/wabt/\n  GIT_TAG "
        + manifest["wabt"]["commit"]
        + ")",
    )

    mem_header = root / "include/wasm2c_rt_mem.h"
    replace(
        mem_header,
        "  typedef struct w2c_env\n  {\n    wasm_rt_memory_t* sandbox_memory_info;\n    wasm_rt_funcref_table_t* sandbox_callback_table;\n  } w2c_env;",
        "  typedef uint32_t (*interspec_wasm_alloc_fn)(void*, uint32_t, uint32_t);\n"
        "  typedef uint32_t (*interspec_wasm_release_fn)(void*, uint32_t);\n"
        "  typedef uint32_t (*interspec_wasm_size_fn)(void*, uint32_t);\n"
        "  typedef uint32_t (*interspec_wasm_reallocate_fn)(void*, uint32_t, uint32_t);\n\n"
        "  typedef struct w2c_env\n  {\n"
        "    wasm_rt_memory_t* sandbox_memory_info;\n"
        "    wasm_rt_funcref_table_t* sandbox_callback_table;\n"
        "    void* interspec_context;\n"
        "    interspec_wasm_alloc_fn interspec_allocate;\n"
        "    interspec_wasm_release_fn interspec_release;\n"
        "    interspec_wasm_size_fn interspec_size;\n"
        "    interspec_wasm_reallocate_fn interspec_reallocate;\n"
        "  } w2c_env;",
    )

    backend = root / "include/rlbox_wasm2c_sandbox.hpp"
    replace(
        backend,
        "  using T_PointerType = uint32_t;\n  using T_ShortType = int16_t;\n\nprivate:",
        "  using T_PointerType = uint32_t;\n"
        "  using T_ShortType = int16_t;\n\n"
        "  T_PointerType reserve_typed_arena(size_t size)\n"
        "  {\n"
        "    return impl_malloc_in_sandbox(size);\n"
        "  }\n\n"
        "  T_PointerType sandbox_address(const void* ptr) const\n"
        "  {\n"
        "    return impl_get_sandboxed_pointer<void*>(ptr);\n"
        "  }\n\n"
        "  void set_interspec_runtime(void* context,\n"
        "                             ::interspec_wasm_alloc_fn allocate,\n"
        "                             ::interspec_wasm_release_fn release,\n"
        "                             ::interspec_wasm_size_fn size,\n"
        "                             ::interspec_wasm_reallocate_fn reallocate)\n"
        "  {\n"
        "    sandbox_memory_env.interspec_context = context;\n"
        "    sandbox_memory_env.interspec_allocate = allocate;\n"
        "    sandbox_memory_env.interspec_release = release;\n"
        "    sandbox_memory_env.interspec_size = size;\n"
        "    sandbox_memory_env.interspec_reallocate = reallocate;\n"
        "  }\n\n"
        "private:",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    apply_backend(Path(args.root).resolve())


if __name__ == "__main__":
    main()
