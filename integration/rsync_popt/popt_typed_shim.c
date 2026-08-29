#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "interspec_popt_u_policy.h"
#include "popt.h"
#include "site_provenance.h"

typedef uint32_t (*interspec_release_fn)(uint32_t);
typedef uint32_t (*interspec_size_fn)(uint32_t);
typedef uint32_t (*interspec_realloc_fn)(uint32_t, uint32_t);

extern uint32_t interspec_site_alloc_slot;
static interspec_release_fn interspec_release;
static interspec_size_fn interspec_size;
static interspec_realloc_fn interspec_realloc;

void interspec_popt_init(uint32_t site_alloc_slot)
{
  interspec_site_alloc_slot = site_alloc_slot;
}

void interspec_popt_init_lifetime(uint32_t site_alloc_slot,
                                  interspec_release_fn release,
                                  interspec_size_fn size,
                                  interspec_realloc_fn reallocate)
{
  interspec_site_alloc_slot = site_alloc_slot;
  interspec_release = release;
  interspec_size = size;
  interspec_realloc = reallocate;
}

__attribute__((noinline)) char* interspec_typed_strdup(const char* src)
{
  if (!src) return NULL;

  const size_t size = strlen(src) + 1;
  if (size > UINT32_MAX) return NULL;

  uint32_t dst = 0;
  INTERSPEC_SITE_POPT_TYPED_STRDUP_BEGIN();
  dst = INTERSPEC_SITE_ALLOC((uint32_t)size);
  INTERSPEC_SITE_POPT_TYPED_STRDUP_END();
  if (!dst) return NULL;

  memcpy((void*)(uintptr_t)dst, src, size);
  return (char*)(uintptr_t)dst;
}

void interspec_typed_free(void* ptr)
{
  if (!ptr) return;

  const uint32_t raw = (uint32_t)(uintptr_t)ptr;
  if (interspec_release && interspec_release(raw)) {
    /* The bump allocator intentionally keeps the physical bytes mapped.  T has
     * removed the authoritative metadata, so stale pointers fail immediately. */
    return;
  }

  free(ptr);
}

void* interspec_typed_realloc(void* ptr, size_t size)
{
  if (!ptr) return realloc(NULL, size);
  if (size > UINT32_MAX) return NULL;

  const uint32_t raw = (uint32_t)(uintptr_t)ptr;
  if (interspec_size && interspec_realloc) {
    const uint32_t old_size = interspec_size(raw);
    if (old_size != 0) {
      if (size == 0) {
        if (interspec_release) interspec_release(raw);
        return NULL;
      }

      const uint32_t dst = interspec_realloc(raw, (uint32_t)size);
      if (!dst) return NULL;

      const size_t copy = old_size < size ? old_size : size;
      memcpy((void*)(uintptr_t)dst, ptr, copy);
      return (void*)(uintptr_t)dst;
    }
  }

  return realloc(ptr, size);
}

char* interspec_popt_get_opt_arg(void* opaque)
{
  /* expandNextArg() is instrumented directly, so the real popt return value
   * already points to a trusted-metadata char allocation. */
  return poptGetOptArg((poptContext)opaque);
}

char* interspec_popt_get_opt_arg_wrong_type(void* opaque)
{
  /* Return a real tracked poptContext pointer as if it were char*.  This keeps
   * the adversarial case independent of any U-selected type identifier. */
  return (char*)opaque;
}

char* interspec_popt_get_opt_arg_untracked(void* opaque)
{
  const char* src = poptGetOptArg((poptContext)opaque);
  if (!src) return NULL;

  const size_t size = strlen(src) + 1;
  char* dst = malloc(size);
  if (!dst) return NULL;

  /* Models a compromised U redirecting the return to a normal sandbox
   * allocation.  The pointer remains in the expected U domain but has no
   * trusted allocation/type record. */
  memcpy(dst, src, size);
  return dst;
}
