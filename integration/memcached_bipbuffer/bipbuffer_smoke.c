#include "bipbuffer.h"
#include "interspec_bipbuffer_u_policy.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern uint32_t interspec_site_alloc_slot;

static uint32_t g_last_size;

void interspec_bipbuf_init(uint32_t site_alloc_slot)
{
    interspec_site_alloc_slot = site_alloc_slot;
}

bipbuf_t *interspec_bipbuf_make_and_fill(void)
{
    static const unsigned char payload[] = "InterSpec-bipbuffer";
    bipbuf_t *buffer = bipbuf_new(64);
    if (buffer == NULL)
        return NULL;
    if (bipbuf_offer(buffer, payload, (int)sizeof(payload)) != (int)sizeof(payload))
        return NULL;
    return buffer;
}

unsigned char *interspec_bipbuf_peek_valid(bipbuf_t *buffer)
{
    unsigned int size = 0;
    unsigned char *ptr = bipbuf_peek_all(buffer, &size);
    g_last_size = size;
    return ptr;
}

/*
 * This is a legitimate tracked boundary-helper allocation, but its trusted
 * type is char rather than bipbuf_t. Returning it where T expects an interior
 * range of a bipbuf_t must fail with wrong_type even though the pointer is in U.
 */
unsigned char *interspec_bipbuf_peek_wrong_type(void)
{
    static const unsigned char bytes[] = "oops";
    uint32_t raw = 0;
    INTERSPEC_SITE_INPUT_COPY_BEGIN();
    raw = INTERSPEC_SITE_ALLOC(sizeof(bytes));
    INTERSPEC_SITE_INPUT_COPY_END();
    if (raw == 0)
        return NULL;
    memcpy((void *)(uintptr_t)raw, bytes, sizeof(bytes));
    g_last_size = (uint32_t)sizeof(bytes);
    return (unsigned char *)(uintptr_t)raw;
}

/* Ordinary U malloc remains in the sandbox domain but has no trusted record. */
unsigned char *interspec_bipbuf_peek_untracked(void)
{
    unsigned char *ptr = (unsigned char *)malloc(8);
    if (ptr == NULL)
        return NULL;
    memset(ptr, 'U', 8);
    g_last_size = 8;
    return ptr;
}

/* Preserve the real interior pointer but corrupt the U-controlled extent. */
unsigned char *interspec_bipbuf_peek_oversized(bipbuf_t *buffer)
{
    unsigned int size = 0;
    unsigned char *ptr = bipbuf_peek_all(buffer, &size);
    if (ptr == NULL)
        return NULL;
    g_last_size = size + 1024;
    return ptr;
}

uint32_t interspec_bipbuf_last_size(void)
{
    return g_last_size;
}
