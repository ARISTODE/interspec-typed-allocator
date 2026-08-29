#include "pcre.h"

#include <stddef.h>

/*
 * CodeQL-only representation of the trusted nginx/libpcre consumption shape.
 * pcre_fullinfo(PCRE_INFO_NAMETABLE) returns an interior pointer into the
 * compiled pcre object. Runtime enforcement is generated from this source-level
 * use policy and executes in the RLBox trusted test.
 */
void interspec_trusted_use_pcre_name_table(const pcre *compiled,
                                           const unsigned char *name_table,
                                           size_t bytes)
{
    (void)compiled;
    if (bytes != 0) {
        volatile unsigned char first = name_table[0];
        volatile unsigned char last = name_table[bytes - 1];
        (void)first;
        (void)last;
    }
}
