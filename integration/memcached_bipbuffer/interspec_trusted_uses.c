#include "bipbuffer.h"

#include <stddef.h>

/*
 * Small source-level representation of T's actual consumption pattern for the
 * P7c boundary analysis.  The pointer returned by bipbuf_peek_all() has byte
 * type, but the security property we need is that the entire consumed range is
 * contained in the live bipbuf_t allocation supplied as owner.
 *
 * The function is compiled into the CodeQL database only. Runtime enforcement
 * happens in the RLBox trusted test/bridge generated from the resulting policy.
 */
void interspec_trusted_use_bipbuf_range(bipbuf_t *owner,
                                        unsigned char *ptr,
                                        size_t len)
{
    (void)owner;
    if (len != 0) {
        volatile unsigned char first = ptr[0];
        volatile unsigned char last = ptr[len - 1];
        (void)first;
        (void)last;
    }
}
