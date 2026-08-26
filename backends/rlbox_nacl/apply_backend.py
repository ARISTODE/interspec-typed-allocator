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
    native = root / "nacl_rlbox/native_client"

    require_head(root, manifest["rlbox_nacl_sandbox"]["commit"])
    require_head(native, manifest["nacl_sandbox_compiler"]["commit"])

    backend = root / "include/rlbox_nacl_sandbox.hpp"
    replace(
        backend,
        "  using T_PointerType = uint32_t;\n  using T_ShortType = short;\n\nprivate:",
        "  using T_PointerType = uint32_t;\n  using T_ShortType = short;\n\n"
        "  T_PointerType reserve_typed_arena(size_t size)\n"
        "  {\n"
        "    return static_cast<T_PointerType>(reserveTypedArena(sandbox, size));\n"
        "  }\n\n"
        "  T_PointerType sandbox_address(const void* ptr) const\n"
        "  {\n"
        "    return static_cast<T_PointerType>(\n"
        "      getSandboxedAddress(sandbox, reinterpret_cast<uintptr_t>(ptr)));\n"
        "  }\n\n"
        "private:",
    )

    sel_ldr = native / "src/trusted/service_runtime/sel_ldr.h"
    replace(
        sel_ldr,
        "  uintptr_t                 break_addr;   /* user addr */\n"
        "  /* data_end <= break_addr is an invariant */",
        "  uintptr_t                 break_addr;   /* user addr */\n"
        "  /* data_end <= break_addr is an invariant */\n\n"
        "  /* T-managed arena that remains readable/writable by U. */\n"
        "  uintptr_t                 typed_arena_start;\n"
        "  size_t                    typed_arena_size;",
    )

    dyn_header = native / "src/trusted/dyn_ldr/dyn_ldr_lib.h"
    replace(
        dyn_header,
        "unsigned long getSandboxMemoryBase(NaClSandbox* sandbox);\n\n"
        "void* mallocInSandbox",
        "unsigned long getSandboxMemoryBase(NaClSandbox* sandbox);\n"
        "uintptr_t reserveTypedArena(NaClSandbox* sandbox, size_t size);\n\n"
        "void* mallocInSandbox",
    )

    dyn_source = native / "src/trusted/dyn_ldr/dyn_ldr_lib.c"
    replace(
        dyn_source,
        "unsigned long getSandboxMemoryBase(NaClSandbox* sandbox)\n"
        "{\n"
        "  return sandbox->nap->mem_start;\n"
        "}\n\n"
        "/********************** \"Function call stub\" helpers *****************************/",
        "unsigned long getSandboxMemoryBase(NaClSandbox* sandbox)\n"
        "{\n"
        "  return sandbox->nap->mem_start;\n"
        "}\n\n"
        "uintptr_t reserveTypedArena(NaClSandbox* sandbox, size_t size)\n"
        "{\n"
        "  if (size == 0 || sandbox->nap->typed_arena_size != 0) return 0;\n\n"
        "  size = NaClRoundAllocPage(size);\n"
        "  uintptr_t addr = (uintptr_t) NaClSysMmapIntern(\n"
        "    sandbox->nap,\n"
        "    (void *) sandbox->nap->data_start,\n"
        "    size,\n"
        "    NACL_ABI_PROT_READ | NACL_ABI_PROT_WRITE,\n"
        "    NACL_ABI_MAP_ANONYMOUS | NACL_ABI_MAP_PRIVATE,\n"
        "    -1,\n"
        "    0);\n\n"
        "  if ((void *) addr == NACL_ABI_MAP_FAILED || NaClPtrIsNegErrno(&addr)) return 0;\n\n"
        "  sandbox->nap->typed_arena_start = addr;\n"
        "  sandbox->nap->typed_arena_size = size;\n"
        "  return addr;\n"
        "}\n\n"
        "/********************** \"Function call stub\" helpers *****************************/",
    )

    sys_memory = native / "src/trusted/service_runtime/sys_memory.c"
    replace(
        sys_memory,
        "static INLINE size_t  size_min(size_t a, size_t b) {\n"
        "  return (a < b) ? a : b;\n"
        "}\n",
        "static INLINE size_t  size_min(size_t a, size_t b) {\n"
        "  return (a < b) ? a : b;\n"
        "}\n\n"
        "static int TypedArenaOverlaps(struct NaClApp *nap,\n"
        "                              uintptr_t start, size_t length) {\n"
        "  if (nap->typed_arena_size == 0 || length == 0) return 0;\n\n"
        "  uintptr_t end = start + length;\n"
        "  if (end < start) return 1;\n"
        "  end = NaClRoundAllocPage(end);\n"
        "  if (end < start) return 1;\n\n"
        "  const uintptr_t arena_end =\n"
        "      nap->typed_arena_start + nap->typed_arena_size;\n"
        "  return start < arena_end && nap->typed_arena_start < end;\n"
        "}\n",
    )
    replace(
        sys_memory,
        "                    uint32_t              offp) {\n"
        "  struct NaClApp  *nap = natp->nap;\n"
        "  nacl_abi_off_t  offset;",
        "                    uint32_t              offp) {\n"
        "  struct NaClApp  *nap = natp->nap;\n"
        "  nacl_abi_off_t  offset;\n\n"
        "  if ((flags & NACL_ABI_MAP_FIXED) &&\n"
        "      TypedArenaOverlaps(nap, start, length)) {\n"
        "    return -NACL_ABI_EINVAL;\n"
        "  }",
    )
    replace(
        sys_memory,
        "int32_t NaClSysMunmap(struct NaClAppThread  *natp,\n"
        "                      uint32_t              start,\n"
        "                      uint32_t              length) {\n"
        "  struct NaClApp *nap = natp->nap;",
        "int32_t NaClSysMunmap(struct NaClAppThread  *natp,\n"
        "                      uint32_t              start,\n"
        "                      uint32_t              length) {\n"
        "  struct NaClApp *nap = natp->nap;\n\n"
        "  if (TypedArenaOverlaps(nap, start, length)) return -NACL_ABI_EINVAL;",
    )
    replace(
        sys_memory,
        "int32_t NaClSysMprotect(struct NaClAppThread  *natp,\n"
        "                        uint32_t              start,\n"
        "                        size_t                length,\n"
        "                        int                   prot) {\n"
        "  struct NaClApp  *nap = natp->nap;",
        "int32_t NaClSysMprotect(struct NaClAppThread  *natp,\n"
        "                        uint32_t              start,\n"
        "                        size_t                length,\n"
        "                        int                   prot) {\n"
        "  struct NaClApp  *nap = natp->nap;\n\n"
        "  if (TypedArenaOverlaps(nap, start, length)) return -NACL_ABI_EINVAL;",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    apply_backend(Path(args.root).resolve())


if __name__ == "__main__":
    main()
