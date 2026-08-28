#include <stdint.h>

/* One allocator callback slot is shared by all generated allocation sites in a
 * sandbox instance.  T initializes it before any instrumented U code runs. */
uint32_t interspec_site_alloc_slot = UINT32_MAX;
