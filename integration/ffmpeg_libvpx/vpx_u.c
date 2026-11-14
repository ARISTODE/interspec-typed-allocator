/* Compiled into U together with libvpx and untrusted/libvpx_shim.c (the shim
 * of the interspec-artifact wrapper, unchanged). T calls most shim functions
 * directly. This file adds staging memory for T's inputs and thin wrappers
 * around the three calls that the policy tests observe or disturb.
 *
 * Addresses cross the boundary as 32-bit values, as in the shim's interface. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "shared/libvpx_bridge_abi.h"

#ifndef INTERSPEC_TRACKING
#define INTERSPEC_TRACKING 0
#endif
#if INTERSPEC_TRACKING
#include "interspec_vpx_u_policy.h"
#endif

vpx_codec_err_t libvpx_rlbox_codec_encode(uint32_t ctx_addr, const libvpx_bridge_image_t *img,
                                          int64_t pts, uint32_t duration, uint32_t flags,
                                          uint32_t deadline);
vpx_codec_err_t libvpx_rlbox_codec_decode(uint32_t ctx_addr, uint32_t data_addr,
                                          uint32_t data_sz, int32_t deadline);
int libvpx_rlbox_codec_get_frame(uint32_t ctx_addr, uint32_t iter_state,
                                 libvpx_bridge_image_t *out_image);

/* Staging memory that T fills or reads: 0 = bridge structures, 1 = raw planes
 * for encode, 2 = compressed data for decode. */
static unsigned char *g_stage[3];
static uint32_t g_stage_capacity[3];

#ifdef INTERSPEC_FAULT_TESTS
static uint32_t g_fault_mode, g_fault_used, g_poc_flags;
/* Fault modes act on plane 0 of the first decoded frame: 1 = live allocation
 * of the wrong type, 2 = untracked heap copy, 3 = released allocation, 4 =
 * live allocation of the right type that is smaller than the plane. */
void interspec_vpx_fault(uint32_t mode) { g_fault_mode = mode; g_fault_used = 0; }
/* Policy-switch tests, same flag bits as the other boundaries:
 * 1 = U reads the image fields that the encoder does not use,
 * 2 = U overwrites its copy of the luma plane after encoding. */
void interspec_vpx_poc(uint32_t flags) { g_poc_flags = flags; }
#endif

unsigned char *interspec_vpx_stage(uint32_t which, uint32_t bytes)
{
    if (which > 2) return NULL;
    if (bytes > g_stage_capacity[which]) {
        free(g_stage[which]);
        g_stage[which] = malloc(bytes);
        g_stage_capacity[which] = g_stage[which] ? bytes : 0;
    }
    return g_stage[which];
}

int interspec_vpx_encode(uint32_t ctx_addr, uint32_t image_addr, long long pts,
                         uint32_t duration, uint32_t flags, uint32_t deadline)
{
    const libvpx_bridge_image_t *img = (const libvpx_bridge_image_t *)(uintptr_t)image_addr;
#ifdef INTERSPEC_FAULT_TESTS
    if (img && img->present && (g_poc_flags & 1u)) {
        fprintf(stderr, "[InterSpec][PoC][SP1] sandbox read image fields user_priv=0x%x "
                        "img_data=0x%x fb_priv=0x%x img_data_owner=%d\n",
                img->user_priv, img->img_data, img->fb_priv, img->img_data_owner);
        fflush(stderr);
    }
#endif
    const int rc = (int)libvpx_rlbox_codec_encode(ctx_addr, img, pts, duration, flags, deadline);
#ifdef INTERSPEC_FAULT_TESTS
    if (rc == 0 && img && img->present && img->planes[0] && (g_poc_flags & 2u)) {
        unsigned char *luma = (unsigned char *)(uintptr_t)img->planes[0];
        const unsigned old = luma[0];
        luma[0] ^= 0xff;
        fprintf(stderr, "[InterSpec][PoC][SP2] sandbox mutated luma byte=0 "
                        "old=0x%02x new=0x%02x\n", old, (unsigned)luma[0]);
        fflush(stderr);
    }
#endif
    return rc;
}

int interspec_vpx_decode(uint32_t ctx_addr, uint32_t data_addr, uint32_t data_sz,
                         int32_t deadline)
{
    return (int)libvpx_rlbox_codec_decode(ctx_addr, data_addr, data_sz, deadline);
}

int interspec_vpx_get_frame(uint32_t ctx_addr, uint32_t iter_state, uint32_t image_addr)
{
    libvpx_bridge_image_t *out = (libvpx_bridge_image_t *)(uintptr_t)image_addr;
    const int rc = libvpx_rlbox_codec_get_frame(ctx_addr, iter_state, out);
#ifdef INTERSPEC_FAULT_TESTS
    if (rc == 1 && out->present && out->planes[0] && g_fault_mode && !g_fault_used &&
        out->stride[0] > 0 && out->d_h > 0) {
        const uint32_t bytes = (uint32_t)out->stride[0] * (out->d_h - 1u) + out->d_w;
        uint32_t replacement = 0, copy = bytes;
        g_fault_used = 1;
        if (g_fault_mode == 2) {
            replacement = (uint32_t)(uintptr_t)malloc(bytes);
        }
#if INTERSPEC_TRACKING
        else if (g_fault_mode == 1) {
            replacement = INTERSPEC_SITE_WRONG_TYPE_ALLOC(bytes);
        } else if (g_fault_mode == 3) {
            replacement = INTERSPEC_SITE_FRAME_BUFFER_ALLOC(bytes);
        } else if (g_fault_mode == 4) {
            copy = bytes / 2;
            replacement = INTERSPEC_SITE_FRAME_BUFFER_ALLOC(copy);
        }
#endif
        if (!replacement) return -100;
        memcpy((void *)(uintptr_t)replacement, (void *)(uintptr_t)out->planes[0], copy);
#if INTERSPEC_TRACKING
        if (g_fault_mode == 3) (void)interspec_wasm_release(replacement);
#endif
        fprintf(stderr, "FAULT_INJECTION boundary=ffmpeg_libvpx mode=%u original=0x%x "
                        "replacement=0x%x bytes=%u\n",
                g_fault_mode, out->planes[0], replacement, bytes);
        fflush(stderr);
        out->planes[0] = replacement;
    }
#endif
    return rc;
}
