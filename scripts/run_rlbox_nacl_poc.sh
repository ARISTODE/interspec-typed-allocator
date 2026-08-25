#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=${TMPDIR:-/tmp}/interspec-rlbox-nacl
rm -rf "$work"

git clone -q https://github.com/PLSysSec/rlbox_nacl_sandbox.git "$work"
git -C "$work" checkout -q 0dd15342c86c0625c7c2ed7762a13feb524252d7

# The upstream .gclient still uses the SSH URL for the public compiler repo.
sed -i 's#git@github.com:PLSysSec/nacl_sandbox_compiler.git#https://github.com/PLSysSec/nacl_sandbox_compiler.git#' \
  "$work/nacl_rlbox/.gclient"
"$work/nacl_rlbox/call_gclient_sync.sh"

generated="$work/interspec-generated"
python3 "$root/tools/generate_policy.py" \
  --policy "$root/policy/poc_policy.json" \
  --source "$root/poc/typed_poc_untrusted.c" \
  --out-dir "$generated"

cp "$generated/typed_poc_untrusted.c" "$work/c_src/"
cp "$generated/interspec_u_policy.h" "$work/c_src/"
cp "$generated/interspec_t_policy.h" "$work/test/"
cp "$root/poc/typed_poc.inc.cpp" "$work/test/"
mkdir -p "$work/test/interspec"
cp "$root/include/interspec/runtime.h" "$work/test/interspec/"

python3 - "$work" <<'PY'
from pathlib import Path
import sys

repo = Path(sys.argv[1])


def replace(path, old, new):
    text = path.read_text()
    assert old in text, f"patch context not found in {path}"
    path.write_text(text.replace(old, new, 1))


root_cmake = repo / "CMakeLists.txt"
replace(
    root_cmake,
    "FetchContent_Declare(\n  rlbox\n  GIT_REPOSITORY https://github.com/PLSysSec/rlbox_api_cpp17.git)",
    "FetchContent_Declare(\n  rlbox\n  GIT_REPOSITORY https://github.com/PLSysSec/rlbox.git\n  GIT_TAG b0157dc84f86ffbe4549e32ed5cbdfad79c17f43)")
replace(
    root_cmake,
    'add_subdirectory("${catch2_SOURCE_DIR}")',
    'add_subdirectory("${catch2_SOURCE_DIR}" "${catch2_BINARY_DIR}")')

cmake = repo / "c_src/CMakeLists.txt"
replace(
    cmake,
    "${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c)",
    "${rlbox_SOURCE_DIR}/code/tests/rlbox_glue/lib/libtest.c\n"
    "               ${CMAKE_SOURCE_DIR}/typed_poc_untrusted.c)")

test = repo / "test/test_nacl_sandbox_glue.cpp"
include = '#include "typed_poc.inc.cpp"\n'
text = test.read_text()
if include not in text:
    test.write_text(text + "\n" + include)

backend = repo / "include/rlbox_nacl_sandbox.hpp"
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
    "private:")

native = repo / "nacl_rlbox/native_client"
sel_ldr = native / "src/trusted/service_runtime/sel_ldr.h"
replace(
    sel_ldr,
    "  uintptr_t                 break_addr;   /* user addr */\n"
    "  /* data_end <= break_addr is an invariant */",
    "  uintptr_t                 break_addr;   /* user addr */\n"
    "  /* data_end <= break_addr is an invariant */\n\n"
    "  /* T-managed arena that remains readable/writable by U. */\n"
    "  uintptr_t                 typed_arena_start;\n"
    "  size_t                    typed_arena_size;")

dyn_header = native / "src/trusted/dyn_ldr/dyn_ldr_lib.h"
replace(
    dyn_header,
    "unsigned long getSandboxMemoryBase(NaClSandbox* sandbox);\n\n"
    "void* mallocInSandbox",
    "unsigned long getSandboxMemoryBase(NaClSandbox* sandbox);\n"
    "uintptr_t reserveTypedArena(NaClSandbox* sandbox, size_t size);\n\n"
    "void* mallocInSandbox")

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
    "/********************** \"Function call stub\" helpers *****************************/")

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
    "}\n")
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
    "  }")
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
    "  if (TypedArenaOverlaps(nap, start, length)) return -NACL_ABI_EINVAL;")
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
    "  if (TypedArenaOverlaps(nap, start, length)) return -NACL_ABI_EINVAL;")
PY

cmake -S "$work" -B "$work/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/build" --target glue_lib_nacl --parallel 2
cmake --build "$work/build" --target test_rlbox_glue --parallel 2
"$work/build/test_rlbox_glue" "[typed_allocator]"
