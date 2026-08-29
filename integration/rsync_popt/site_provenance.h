#pragma once

#include <stdint.h>

/*
 * Transitional P7b compatibility aliases.  The authoritative helper-site
 * definition is moving to boundary.json and generate_boundary_policy.py.
 * Existing RLBox/P4c code uses these aliases until the real integration is
 * switched to the combined generated allocation policy.
 */
#define INTERSPEC_POPT_STRDUP_SITE_ID UINT32_C(3)
#define INTERSPEC_POPT_STRDUP_BEGIN_SYMBOL \
  "interspec_alloc_site_popt_typed_strdup_3_begin"
#define INTERSPEC_POPT_STRDUP_END_SYMBOL \
  "interspec_alloc_site_popt_typed_strdup_3_end"

#define INTERSPEC_SITE_POPT_TYPED_STRDUP_BEGIN() \
  __asm__ __volatile__( \
    ".globl interspec_alloc_site_popt_typed_strdup_3_begin\n" \
    ".type interspec_alloc_site_popt_typed_strdup_3_begin,@function\n" \
    "interspec_alloc_site_popt_typed_strdup_3_begin:" \
    ::: "memory")

#define INTERSPEC_SITE_POPT_TYPED_STRDUP_END() \
  __asm__ __volatile__( \
    ".globl interspec_alloc_site_popt_typed_strdup_3_end\n" \
    ".type interspec_alloc_site_popt_typed_strdup_3_end,@function\n" \
    "interspec_alloc_site_popt_typed_strdup_3_end:" \
    ::: "memory")
