/* Compiled into U together with libzip, zlib and zip_shim.c (the shim of the
 * interspec-artifact wrapper, unchanged). The trusted side sees the shim's
 * interface,
 *   ziplib_stat_and_get_names(za, idx, &size, &name_direct, &name_stat),
 * split into calls whose arguments are scalars or a U staging buffer.
 *
 * The two names point into libzip's own memory. In the tracked builds the
 * buffer of every zip_string_t is allocated from a site that the trusted
 * registry knows (see policy.json and scripts/build_zip_port.sh), so T can
 * check live object, type and bounds before it reads a name. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "zip_shim.h"

#ifndef INTERSPEC_TRACKING
#define INTERSPEC_TRACKING 0
#endif
#if INTERSPEC_TRACKING
#include "interspec_zip_u_policy.h"
#endif

#ifdef __wasm__
#include <errno.h>
/* See zip_wasi_compat.h: nothing in the sandbox writes files. */
int chmod(const char *path, mode_t mode)
{
    (void)path; (void)mode;
    errno = ENOSYS;
    return -1;
}
#endif

static unsigned char *g_archive;
static uint32_t g_archive_capacity;
static zip_source_t *g_source;
static zip_t *g_za;
/* The three out-parameters of the shim call. */
static zip_uint64_t g_size;
static const char *g_name[2];

#ifdef INTERSPEC_FAULT_TESTS
static uint32_t g_fault_mode, g_fault_used, g_poc_flags;
/* Fault modes act on the first name returned: 1 = live allocation of the
 * wrong type, 2 = untracked heap copy, 3 = released allocation, 4 = live
 * allocation of the right type that holds the name without its terminator. */
void interspec_zip_fault(uint32_t mode) { g_fault_mode = mode; g_fault_used = 0; }
/* Policy-switch tests, same flag bits as the other boundaries:
 * 1 = U reads what it was handed for the three out-parameters,
 * 2 = U overwrites its copy of the archive after opening it. */
void interspec_zip_poc(uint32_t flags) { g_poc_flags = flags; }
#endif

unsigned char *interspec_zip_setup(uint32_t capacity)
{
    g_archive = malloc(capacity ? capacity : 1);
    g_archive_capacity = g_archive ? capacity : 0;
    return g_archive;
}

/* 64-bit values cross the boundary as (unsigned) long long: RLBox maps types
 * by name, and long is 32 bits wide inside the sandbox.
 *
 * Opens the archive that T copied into the staging buffer. Returns the number
 * of entries, or a negative value. */
long long interspec_zip_open(uint32_t len)
{
    zip_error_t error;
    if (!g_archive || !len || len > g_archive_capacity || g_za) return -1;
    zip_error_init(&error);
    g_source = zip_source_buffer_create(g_archive, len, 0, &error);
    if (!g_source) { zip_error_fini(&error); return -2; }
    g_za = zip_open_from_source(g_source, ZIP_RDONLY, &error);
    zip_error_fini(&error);
    if (!g_za) {
        zip_source_free(g_source);
        g_source = NULL;
        return -3;
    }
#ifdef INTERSPEC_FAULT_TESTS
    if (g_poc_flags & 2u) {
        const unsigned old = g_archive[0];
        g_archive[0] ^= 0xff;
        fprintf(stderr, "[InterSpec][PoC][SP2] sandbox mutated archive byte=0 "
                        "old=0x%02x new=0x%02x\n", old, (unsigned)g_archive[0]);
        fflush(stderr);
    }
#endif
    return zip_get_num_entries(g_za, 0);
}

/* size_in, name_direct_in and name_stat_in are what the wrapper copied in for
 * the out-parameters. Nothing in libzip or the shim reads them. Returns the
 * shim's return value. */
int interspec_zip_stat_and_get_names(unsigned long long idx, unsigned long long size_in,
                                     uint32_t name_direct_in, uint32_t name_stat_in)
{
    g_size = size_in;
    g_name[0] = (const char *)(uintptr_t)name_direct_in;
    g_name[1] = (const char *)(uintptr_t)name_stat_in;
#ifdef INTERSPEC_FAULT_TESTS
    if (g_poc_flags & 1u) {
        fprintf(stderr, "[InterSpec][PoC][SP1] sandbox read out-parameters "
                        "size_in=0x%llx name_direct_in=0x%x name_stat_in=0x%x\n",
                (unsigned long long)g_size, name_direct_in, name_stat_in);
        fflush(stderr);
    }
#endif
    const int rc = ziplib_stat_and_get_names(g_za, idx, &g_size, &g_name[0], &g_name[1]);

#ifdef INTERSPEC_FAULT_TESTS
    if (rc == 0 && g_fault_mode && !g_fault_used && g_name[0]) {
        const uint32_t size = (uint32_t)strlen(g_name[0]);
        uint32_t replacement = 0;
        g_fault_used = 1;
        if (g_fault_mode == 1) {
#if INTERSPEC_TRACKING
            replacement = INTERSPEC_SITE_WRONG_TYPE_ALLOC(size + 1);
#endif
        } else if (g_fault_mode == 2) {
            replacement = (uint32_t)(uintptr_t)malloc(size + 1);
        } else if (g_fault_mode == 3) {
#if INTERSPEC_TRACKING
            replacement = INTERSPEC_SITE_CONVERTED_NAME_ALLOC(size + 1);
#endif
        } else if (g_fault_mode == 4) {
#if INTERSPEC_TRACKING
            replacement = INTERSPEC_SITE_CONVERTED_NAME_ALLOC(size ? size : 1);
#endif
        }
        if (!replacement) return -100;
        if (g_fault_mode == 4) {
            if (size) memcpy((void *)(uintptr_t)replacement, g_name[0], size);
            else *(char *)(uintptr_t)replacement = 'x';
        } else {
            memcpy((void *)(uintptr_t)replacement, g_name[0], size + 1);
        }
#if INTERSPEC_TRACKING
        if (g_fault_mode == 3) (void)interspec_wasm_release(replacement);
#endif
        fprintf(stderr, "FAULT_INJECTION boundary=zip_libzip mode=%u original=0x%x "
                        "replacement=0x%x bytes=%u\n",
                g_fault_mode, (uint32_t)(uintptr_t)g_name[0], replacement, size);
        fflush(stderr);
        g_name[0] = (const char *)(uintptr_t)replacement;
    }
#endif
    return rc;
}

unsigned long long interspec_zip_size(void) { return g_size; }

const char *interspec_zip_name(uint32_t which)
{
    return which < 2 ? g_name[which] : NULL;
}

void interspec_zip_close(void)
{
    if (g_za) zip_close(g_za);   /* also releases the source */
    g_za = NULL;
    g_source = NULL;
    g_name[0] = g_name[1] = NULL;
    free(g_archive);
    g_archive = NULL;
    g_archive_capacity = 0;
}
