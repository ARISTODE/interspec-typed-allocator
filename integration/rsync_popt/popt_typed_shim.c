#include <stdint.h>

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
