#pragma once

#include <stdint.h>

/*
 * Transitional P7b compatibility aliases.  The authoritative helper-site
 * definition now lives in boundary.json and is emitted by
 * generate_boundary_policy.py.  Existing bridge code can use these names until
 * it is migrated to register_allocation_policy().
 */
#define INTERSPEC_POPT_STRDUP_SITE_ID UINT32_C(3)
#define INTERSPEC_POPT_STRDUP_BEGIN_SYMBOL \
  "interspec_alloc_site_popt_typed_strdup_3_begin"
#define INTERSPEC_POPT_STRDUP_END_SYMBOL \
  "interspec_alloc_site_popt_typed_strdup_3_end"
