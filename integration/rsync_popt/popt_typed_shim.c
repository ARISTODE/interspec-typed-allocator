#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "interspec_popt_u_policy.h"
#include "popt.h"

typedef uint32_t (*interspec_alloc_fn)(uint32_t, uint32_t);

static interspec_alloc_fn interspec_alloc;

void interspec_popt_init(interspec_alloc_fn alloc)
{
  interspec_alloc = alloc;
}

uint32_t typed_alloc(uint32_t size, uint32_t type_id)
{
  return interspec_alloc ? interspec_alloc(size, type_id) : 0;
}

char* interspec_popt_get_opt_arg(void* opaque)
{
  /* expandNextArg() is instrumented directly, so the real popt return value
   * already points to a trusted-metadata char allocation. */
  return poptGetOptArg((poptContext)opaque);
}

char* interspec_popt_get_opt_arg_wrong_type(void* opaque)
{
  const char* src = poptGetOptArg((poptContext)opaque);
  if (!src) return NULL;

  const size_t size = strlen(src) + 1;
  const uint32_t dst =
    typed_alloc((uint32_t)size, INTERSPEC_TYPE_ID_POPTCONTEXT_S);
  if (!dst) return NULL;

  memcpy((void*)(uintptr_t)dst, src, size);
  return (char*)(uintptr_t)dst;
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
