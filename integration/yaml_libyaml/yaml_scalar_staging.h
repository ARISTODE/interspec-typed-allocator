#ifndef INTERSPEC_YAML_SCALAR_STAGING_H
#define INTERSPEC_YAML_SCALAR_STAGING_H

#include <stddef.h>
#include <stdint.h>

#define INTERSPEC_YAML_STAGING_CAPACITY UINT32_C(8192)

/* One typed element is this whole staging object, not an individual byte. */
typedef struct interspec_yaml_scalar_staging {
    unsigned char payload[INTERSPEC_YAML_STAGING_CAPACITY];
} interspec_yaml_scalar_staging;

#ifdef __cplusplus
static_assert(offsetof(interspec_yaml_scalar_staging, payload) == 0,
              "scalar payload must start at the object base");
static_assert(sizeof(interspec_yaml_scalar_staging) == 8192,
              "scalar staging ABI size");
static_assert(alignof(interspec_yaml_scalar_staging) == 1,
              "scalar staging ABI alignment");
#else
_Static_assert(offsetof(interspec_yaml_scalar_staging, payload) == 0,
               "scalar payload must start at the object base");
_Static_assert(sizeof(interspec_yaml_scalar_staging) == 8192,
               "scalar staging ABI size");
_Static_assert(_Alignof(interspec_yaml_scalar_staging) == 1,
               "scalar staging ABI alignment");
#endif

#endif
