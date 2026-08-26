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
  char* src = poptGetOptArg((poptContext)opaque);
  if (!src) return NULL;

  const size_t size = strlen(src) + 1;
  const uint32_t dst = typed_alloc((uint32_t)size, INTERSPEC_TYPE_ID_CHAR);
  if (!dst) {
    free(src);
    return NULL;
  }

  memcpy((void*)(uintptr_t)dst, src, size);
  free(src);
  return (char*)(uintptr_t)dst;
}
