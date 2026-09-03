#include "bipbuffer.h"
#include "interspec_bipbuffer_u_policy.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static uint32_t g_last_size;

bipbuf_t *interspec_wasm_bipbuf_make_and_fill(void)
{
    static const unsigned char payload[] = "InterSpec-bipbuffer";
    bipbuf_t *buffer = bipbuf_new(64);
    if (buffer == NULL)
        return NULL;
    if (bipbuf_offer(buffer, payload, (int)sizeof(payload)) != (int)sizeof(payload))
        return NULL;
    return buffer;
}

unsigned char *interspec_wasm_bipbuf_peek_valid(bipbuf_t *buffer)
{
    unsigned int size = 0;
    unsigned char *ptr = bipbuf_peek_all(buffer, &size);
    g_last_size = size;
    return ptr;
}

unsigned char *interspec_wasm_bipbuf_peek_wrong_type(void)
{
    static const unsigned char bytes[] = "oops";
    uint32_t raw = INTERSPEC_SITE_INPUT_COPY_ALLOC(sizeof(bytes));
    if (raw == 0)
        return NULL;
    memcpy((void *)(uintptr_t)raw, bytes, sizeof(bytes));
    g_last_size = (uint32_t)sizeof(bytes);
    return (unsigned char *)(uintptr_t)raw;
}

unsigned char *interspec_wasm_bipbuf_peek_untracked(void)
{
    unsigned char *ptr = (unsigned char *)malloc(8);
    if (ptr == NULL)
        return NULL;
    memset(ptr, 'U', 8);
    g_last_size = 8;
    return ptr;
}

unsigned char *interspec_wasm_bipbuf_peek_oversized(bipbuf_t *buffer)
{
    unsigned int size = 0;
    unsigned char *ptr = bipbuf_peek_all(buffer, &size);
    if (ptr == NULL)
        return NULL;
    g_last_size = size + 1024;
    return ptr;
}

uint32_t interspec_wasm_bipbuf_last_size(void)
{
    return g_last_size;
}
