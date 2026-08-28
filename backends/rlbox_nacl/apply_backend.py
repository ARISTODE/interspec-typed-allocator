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

    # The pinned NaCl backend predates rlbox_stdlib.hpp's rlbox::memcpy helper.
    # Its old unqualified memcpy calls execute inside namespace rlbox and would
    # otherwise resolve only to the newer four-argument RLBox helper. Make the
    # ordinary three-argument C++ memcpy overload visible in the same namespace.
    replace(
        backend,
        "#include <cstdint>\n#include <iostream>",
        "#include <cstdint>\n#include <cstring>\n#include <iostream>",
    )
    replace(
        backend,
        "namespace rlbox {\n\nnamespace detail {",
        "namespace rlbox {\n\nusing std::memcpy;\n\nnamespace detail {",
    )

    replace(
        backend,
        "  using T_PointerType = uint32_t;\n  using T_ShortType = short;\n\nprivate:",
        "  using T_PointerType = uint32_t;\n"
        "  using T_ShortType = short;\n\n"
        "  T_PointerType reserve_typed_arena(size_t size)\n"
        "  {\n"
        "    return static_cast<T_PointerType>(reserveTypedArena(sandbox, size));\n"
        "  }\n\n"
        "  T_PointerType sandbox_address(const void* ptr) const\n"
        "  {\n"
        "    return static_cast<T_PointerType>(\n"
        "      getSandboxedAddress(sandbox, reinterpret_cast<uintptr_t>(ptr)));\n"
        "  }\n\n"
        "  uintptr_t callback_program_counter() const\n"
        "  {\n"
        "    return getCallbackProgramCounter(sandbox);\n"
        "  }\n\n"
        "  uintptr_t callback_new_program_counter() const\n"
        "  {\n"
        "    return getCallbackNewProgramCounter(sandbox);\n"
        "  }\n\n"
        "  uint32_t callback_slot_for_key(const void* key) const\n"
        "  {\n"
        "    RLBOX_ACQUIRE_SHARED_GUARD(lock, callback_mutex);\n"
        "    for (uint32_t i = 0; i < MAX_CALLBACKS; ++i) {\n"
        "      if (callback_unique_keys[i] == key) return i;\n"
        "    }\n"
        "    return std::numeric_limits<uint32_t>::max();\n"
        "  }\n\n"
        "  uintptr_t lookup_symbol_address(const char* name)\n"
        "  {\n"
        "    return reinterpret_cast<uintptr_t>(impl_lookup_symbol(name));\n"
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
        "\tsize_t callbackParamsAlreadyRead;\n",
        "\tsize_t callbackParamsAlreadyRead;\n"
        "\t/* Trusted NaCl execution state captured at callback syscall entry. */\n"
        "\tuintptr_t callbackProgramCounter;\n"
        "\tuintptr_t callbackNewProgramCounter;\n",
    )
    replace(
        dyn_header,
        "unsigned long getSandboxMemoryBase(NaClSandbox* sandbox);\n\n"
        "void* mallocInSandbox",
        "unsigned long getSandboxMemoryBase(NaClSandbox* sandbox);\n"
        "uintptr_t reserveTypedArena(NaClSandbox* sandbox, size_t size);\n"
        "uintptr_t getCallbackProgramCounter(NaClSandbox* sandbox);\n"
        "uintptr_t getCallbackNewProgramCounter(NaClSandbox* sandbox);\n\n"
        "void* mallocInSandbox",
    )

    dyn_source = native / "src/trusted/dyn_ldr/dyn_ldr_lib.c"
    replace(
        dyn_source,
        "  threadData->callbackParamsAlreadyRead = 0;\n",
        "  threadData->callbackParamsAlreadyRead = 0;\n"
        "  threadData->callbackProgramCounter = 0;\n"
        "  threadData->callbackNewProgramCounter = 0;\n",
    )
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
    replace(
        dyn_source,
        "NaClSandbox_Thread* callbackParamsBegin(NaClSandbox* sandbox)\n",
        "uintptr_t getCallbackProgramCounter(NaClSandbox* sandbox)\n"
        "{\n"
        "  NaClSandbox_Thread* threadData = getThreadData(sandbox);\n"
        "  return threadData ? threadData->callbackProgramCounter : 0;\n"
        "}\n\n"
        "uintptr_t getCallbackNewProgramCounter(NaClSandbox* sandbox)\n"
        "{\n"
        "  NaClSandbox_Thread* threadData = getThreadData(sandbox);\n"
        "  return threadData ? threadData->callbackNewProgramCounter : 0;\n"
        "}\n\n"
        "NaClSandbox_Thread* callbackParamsBegin(NaClSandbox* sandbox)\n",
    )

    syscall_common = native / "src/trusted/service_runtime/nacl_syscall_common.c"
    replace(
        syscall_common,
        '#include "native_client/src/trusted/dyn_ldr/datastructures/ds_stack.h"\n',
        '#include "native_client/src/trusted/dyn_ldr/datastructures/ds_stack.h"\n'
        '#include "native_client/src/trusted/dyn_ldr/dyn_ldr_lib.h"\n',
    )
    replace(
        syscall_common,
        "  if(callbackSlotNumber < CALLBACK_SLOTS_AVAILABLE && natp->nap->callbackSlot[callbackSlotNumber] != 0)\n"
        "  {\n"
        "    typedef void (*RegPtrPtrFunc)(uintptr_t, void*, uint64_t*);",
        "  if(callbackSlotNumber < CALLBACK_SLOTS_AVAILABLE && natp->nap->callbackSlot[callbackSlotNumber] != 0)\n"
        "  {\n"
        "    typedef void (*RegPtrPtrFunc)(uintptr_t, void*, uint64_t*);\n"
        "    NaClSandbox_Thread* interspecThreadData =\n"
        "      (NaClSandbox_Thread*) natp->custom_app_state;\n"
        "    if (interspecThreadData != NULL) {\n"
        "      interspecThreadData->callbackProgramCounter = natp->user.prog_ctr;\n"
        "      interspecThreadData->callbackNewProgramCounter = natp->user.new_prog_ctr;\n"
        "    }",
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