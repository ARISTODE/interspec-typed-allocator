#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "interspec_popt_u_policy.h"
#include "popt.h"

__attribute__((noinline)) char* interspec_typed_strdup(const char* src)
{
  if (!src) return NULL;

  const size_t size = strlen(src) + 1;
  if (size > UINT32_MAX) return NULL;

  const uint32_t dst = INTERSPEC_SITE_POPT_TYPED_STRDUP_ALLOC((uint32_t)size);
  if (!dst) return NULL;

  memcpy((void*)(uintptr_t)dst, src, size);
  return (char*)(uintptr_t)dst;
}

void interspec_typed_free(void* ptr)
{
  if (!ptr) return;

  const uint32_t raw = (uint32_t)(uintptr_t)ptr;
  if (interspec_wasm_release(raw)) {
    /* T removed the authoritative metadata; the reserved Wasm block remains. */
    return;
  }

  free(ptr);
}

void* interspec_typed_realloc(void* ptr, size_t size)
{
  if (!ptr) return realloc(NULL, size);
  if (size > UINT32_MAX) return NULL;

  const uint32_t raw = (uint32_t)(uintptr_t)ptr;
  const uint32_t old_size = interspec_wasm_size(raw);
  if (old_size != 0) {
    if (size == 0) {
      interspec_wasm_release(raw);
      return NULL;
    }

    const uint32_t dst = interspec_wasm_reallocate(raw, (uint32_t)size);
    if (!dst) return NULL;

    const size_t copy = old_size < size ? old_size : size;
    memcpy((void*)(uintptr_t)dst, ptr, copy);
    return (void*)(uintptr_t)dst;
  }

  return realloc(ptr, size);
}

char* interspec_popt_get_opt_arg(void* opaque)
{
  return poptGetOptArg((poptContext)opaque);
}

char* interspec_popt_get_opt_arg_wrong_type(void* opaque)
{
  return (char*)opaque;
}

char* interspec_popt_get_opt_arg_untracked(void* opaque)
{
  const char* src = poptGetOptArg((poptContext)opaque);
  if (!src) return NULL;

  const size_t size = strlen(src) + 1;
  char* dst = malloc(size);
  if (!dst) return NULL;
  memcpy(dst, src, size);
  return dst;
}
