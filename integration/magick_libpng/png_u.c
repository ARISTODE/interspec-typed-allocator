/* Compiled into U together with libpng, zlib and magick_png_shim.c. The
 * trusted side sees the interface of the interspec-artifact wrapper,
 *   decode_rgba(png, png_len, &w, &h, &rgba, &rgba_len)
 *   encode_rgba(rgba, w, h, &png, &png_len)
 * split into calls whose arguments are scalars or U staging buffers. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "magick_png_shim.h"

#ifndef INTERSPEC_TRACKING
#define INTERSPEC_TRACKING 0
#endif
#if INTERSPEC_TRACKING
#include "interspec_png_u_policy.h"
#endif

/* Staging buffers that T fills: 0 = PNG bytes to decode, 1 = pixels to encode. */
static unsigned char *g_input[2];
static uint32_t g_input_capacity[2];
/* Out-parameters of the two shim calls. */
static uint32_t g_width, g_height, g_size[2];
static unsigned char *g_result[2];

#ifdef INTERSPEC_FAULT_TESTS
static uint32_t g_fault_mode, g_fault_used, g_poc_flags;
/* Fault modes act on the first decoded-pixels pointer: 1 = live allocation of
 * the wrong type, 2 = untracked heap copy, 3 = released allocation, 4 = live
 * allocation of the right type that is smaller than the reported size. */
void interspec_png_fault(uint32_t mode) { g_fault_mode = mode; g_fault_used = 0; }
/* Policy-switch tests, same flag bits as the other boundaries:
 * 1 = U reads what it was handed for the out-parameters of decode,
 * 2 = U overwrites its copy of the PNG bytes after decoding. */
void interspec_png_poc(uint32_t flags) { g_poc_flags = flags; }
#endif

unsigned char *interspec_png_input(uint32_t which, uint32_t capacity)
{
    if (which > 1) return NULL;
    if (capacity > g_input_capacity[which]) {
        free(g_input[which]);
        g_input[which] = malloc(capacity);
        g_input_capacity[which] = g_input[which] ? capacity : 0;
    }
    return g_input[which];
}

/* w_in, h_in, rgba_in and size_in are what the wrapper copied in for the
 * out-parameters. Nothing in libpng or the shim reads them. Returns the
 * decoded pixels, or NULL. */
unsigned char *interspec_png_decode(uint32_t input_len, uint32_t w_in, uint32_t h_in,
                                    uint32_t rgba_in, uint32_t size_in)
{
    g_width = w_in;
    g_height = h_in;
    g_size[0] = size_in;
    g_result[0] = (unsigned char *)(uintptr_t)rgba_in;
#ifdef INTERSPEC_FAULT_TESTS
    if (g_poc_flags & 1u) {
        fprintf(stderr, "[InterSpec][PoC][SP1] sandbox read out-parameters w_in=0x%x "
                        "h_in=0x%x rgba_in=0x%x size_in=0x%x\n",
                g_width, g_height, rgba_in, g_size[0]);
        fflush(stderr);
    }
#endif
    if (!g_input[0] || !input_len || input_len > g_input_capacity[0]) return NULL;
    g_result[0] = magickpng_decode_rgba(g_input[0], input_len, &g_width, &g_height,
                                        &g_size[0]);
#ifdef INTERSPEC_FAULT_TESTS
    if (g_result[0] && (g_poc_flags & 2u)) {
        const unsigned old = g_input[0][0];
        g_input[0][0] ^= 0xff;
        fprintf(stderr, "[InterSpec][PoC][SP2] sandbox mutated png byte=0 "
                        "old=0x%02x new=0x%02x\n", old, (unsigned)g_input[0][0]);
        fflush(stderr);
    }
    if (g_result[0] && g_fault_mode && !g_fault_used) {
        const uint32_t size = g_size[0];
        uint32_t replacement = 0, copy = size;
        g_fault_used = 1;
        if (g_fault_mode == 2) {
            replacement = (uint32_t)(uintptr_t)malloc(size);
        }
#if INTERSPEC_TRACKING
        else if (g_fault_mode == 1) {
            replacement = INTERSPEC_SITE_WRONG_TYPE_ALLOC(size);
        } else if (g_fault_mode == 3) {
            replacement = INTERSPEC_SITE_DECODED_PIXELS_ALLOC(size);
        } else if (g_fault_mode == 4) {
            copy = size / 2;
            replacement = INTERSPEC_SITE_DECODED_PIXELS_ALLOC(copy);
        }
#endif
        if (!replacement) return NULL;
        memcpy((void *)(uintptr_t)replacement, g_result[0], copy);
#if INTERSPEC_TRACKING
        if (g_fault_mode == 3) (void)interspec_wasm_release(replacement);
#endif
        fprintf(stderr, "FAULT_INJECTION boundary=magick_libpng mode=%u original=0x%x "
                        "replacement=0x%x bytes=%u\n",
                g_fault_mode, (uint32_t)(uintptr_t)g_result[0], replacement, size);
        fflush(stderr);
        g_result[0] = (unsigned char *)(uintptr_t)replacement;
    }
#endif
    return g_result[0];
}

/* png_in and size_in are what the wrapper copied in for the out-parameters.
 * Returns the encoded PNG, or NULL. */
unsigned char *interspec_png_encode(uint32_t width, uint32_t height, uint32_t png_in,
                                    uint32_t size_in)
{
    g_size[1] = size_in;
    g_result[1] = (unsigned char *)(uintptr_t)png_in;
    if (!g_input[1] || !width || !height || width > g_input_capacity[1] / 4u / height)
        return NULL;
    g_result[1] = magickpng_encode_rgba(g_input[1], width, height, &g_size[1]);
    return g_result[1];
}

uint32_t interspec_png_width(void) { return g_width; }
uint32_t interspec_png_height(void) { return g_height; }
uint32_t interspec_png_size(uint32_t which) { return which < 2 ? g_size[which] : 0; }

/* T is done with a returned buffer (magickpng_free of the artifact wrapper). */
void interspec_png_done(uint32_t which)
{
    if (which < 2) magickpng_free(g_result[which]);
}
