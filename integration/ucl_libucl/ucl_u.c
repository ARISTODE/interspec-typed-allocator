/* Compiled into U together with libucl. The trusted side sees the interface
 * of the interspec-artifact wrapper,
 *   ucllib_parse_query_emit(input, len, key1, key2, &val1, &val2, &emitted),
 * split into calls whose arguments are scalars or U staging buffers. The two
 * looked-up strings and the emitted document are returned from allocations
 * that the trusted registry knows (helper sites), so that T can check live
 * object, type and bounds before it copies them. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <ucl.h>

#ifndef INTERSPEC_TRACKING
#define INTERSPEC_TRACKING 0
#endif
#if INTERSPEC_TRACKING
#include "interspec_ucl_u_policy.h"
#endif

#ifdef __wasm__
#include <errno.h>
/* See ucl_wasi_compat.h: there is no filesystem inside the sandbox. */
char *realpath(const char *path, char *resolved_path)
{
    (void)path; (void)resolved_path;
    errno = ENOSYS;
    return NULL;
}
#endif

#define KEY_CAPACITY 256u

static unsigned char *g_input;
static uint32_t g_input_capacity;
static char g_keys[2][KEY_CAPACITY];
static uint32_t g_value[3];      /* 0, 1: looked-up strings; 2: emitted */
static uint32_t g_value_size[3];
static uint32_t g_return[3];     /* what U hands to T; differs under a fault */
static uint32_t g_return_size[3];

#ifdef INTERSPEC_FAULT_TESTS
static uint32_t g_fault_mode, g_fault_used, g_poc_flags;
/* Fault modes act on the first looked-up string: 1 = live allocation of the
 * wrong type, 2 = untracked heap copy, 3 = released allocation, 4 = length
 * beyond the allocation, 5 = another live allocation of the same type. */
void interspec_ucl_fault(uint32_t mode) { g_fault_mode = mode; g_fault_used = 0; }
/* Policy-switch tests, same flag bits as the other boundaries:
 * 1 = U reads what it was handed for the three out-parameters,
 * 2 = U overwrites its copy of the document after parsing. */
void interspec_ucl_poc(uint32_t flags) { g_poc_flags = flags; }
#endif

static uint32_t value_alloc(uint32_t which, uint32_t bytes)
{
#if INTERSPEC_TRACKING
    return which == 2 ? INTERSPEC_SITE_EMITTED_ALLOC(bytes)
                      : INTERSPEC_SITE_STRING_VALUE_ALLOC(bytes);
#else
    (void)which;
    return (uint32_t)(uintptr_t)malloc(bytes);
#endif
}

static void value_release(uint32_t ptr)
{
    if (!ptr) return;
#if INTERSPEC_TRACKING
    (void)interspec_wasm_release(ptr);
#else
    free((void *)(uintptr_t)ptr);
#endif
}

static void clear_values(void)
{
    for (int i = 0; i < 3; ++i) {
        value_release(g_value[i]);
        g_value[i] = g_value_size[i] = g_return[i] = g_return_size[i] = 0;
    }
}

unsigned char *interspec_ucl_setup(uint32_t input_capacity)
{
    g_input = malloc(input_capacity ? input_capacity : 1);
    g_input_capacity = g_input ? input_capacity : 0;
    return g_input;
}

char *interspec_ucl_key_buffer(uint32_t which)
{
    return which < 2 ? g_keys[which] : NULL;
}

static int stage(uint32_t which, const unsigned char *bytes, uint32_t size)
{
    uint32_t ptr = value_alloc(which, size + 1);
    if (!ptr) return 0;
    memcpy((void *)(uintptr_t)ptr, bytes, size);
    ((unsigned char *)(uintptr_t)ptr)[size] = 0;
    g_value[which] = g_return[which] = ptr;
    g_value_size[which] = g_return_size[which] = size;
    return 1;
}

/* out_in[0..2] are what the wrapper copied in for the out-parameters val1,
 * val2 and emitted. Nothing in libucl or this shim reads them. Returns 1 on
 * success, 0 on a parse or allocation failure. */
int interspec_ucl_parse(uint32_t input_len, uint32_t out_in1, uint32_t out_in2,
                        uint32_t out_in3)
{
    clear_values();
#ifdef INTERSPEC_FAULT_TESTS
    if (g_poc_flags & 1u) {
        fprintf(stderr, "[InterSpec][PoC][SP1] sandbox read out-parameters "
                        "val1_in=0x%x val2_in=0x%x emitted_in=0x%x\n",
                out_in1, out_in2, out_in3);
        fflush(stderr);
    }
#else
    (void)out_in1; (void)out_in2; (void)out_in3;
#endif
    if (!g_input || !input_len || input_len > g_input_capacity) return 0;
    g_keys[0][KEY_CAPACITY - 1] = g_keys[1][KEY_CAPACITY - 1] = 0;

    struct ucl_parser *parser = ucl_parser_new(0);
    if (!parser) return 0;
    int ok = 0;
    ucl_object_t *root = NULL;
    unsigned char *rendered = NULL;
    if (!ucl_parser_add_chunk(parser, g_input, (size_t)input_len)) goto done;
    root = ucl_parser_get_object(parser);
    if (!root) goto done;
    for (uint32_t i = 0; i < 2; ++i) {
        const ucl_object_t *found = ucl_object_lookup_path_char(root, g_keys[i], '.');
        const char *text = found ? ucl_object_tostring(found) : NULL;
        if (text && !stage(i, (const unsigned char *)text, (uint32_t)strlen(text)))
            goto done;
    }
    rendered = ucl_object_emit(root, UCL_EMIT_JSON_COMPACT);
    if (!rendered || !stage(2, rendered, (uint32_t)strlen((const char *)rendered)))
        goto done;
    ok = 1;
done:
    free(rendered);
    if (root) ucl_object_unref(root);
    ucl_parser_free(parser);

#ifdef INTERSPEC_FAULT_TESTS
    if (ok && (g_poc_flags & 2u)) {
        const unsigned old = g_input[0];
        g_input[0] ^= 0xff;
        fprintf(stderr, "[InterSpec][PoC][SP2] sandbox mutated document byte=0 "
                        "old=0x%02x new=0x%02x\n", old, (unsigned)g_input[0]);
        fflush(stderr);
    }
    if (ok && g_fault_mode && !g_fault_used && g_value[0]) {
        const uint32_t size = g_value_size[0];
        uint32_t replacement = g_value[0];
        g_fault_used = 1;
        if (g_fault_mode == 1) {
#if INTERSPEC_TRACKING
            replacement = INTERSPEC_SITE_WRONG_TYPE_ALLOC(size + 1);
#else
            replacement = (uint32_t)(uintptr_t)malloc(size + 1);
#endif
        } else if (g_fault_mode == 2) {
            replacement = (uint32_t)(uintptr_t)malloc(size + 1);
        } else if (g_fault_mode == 3 || g_fault_mode == 5) {
            replacement = value_alloc(0, size + 1);
        }
        if (!replacement) return 0;
        if (replacement != g_value[0])
            memcpy((void *)(uintptr_t)replacement, (void *)(uintptr_t)g_value[0], size + 1);
        if (g_fault_mode == 3) value_release(replacement);
        if (g_fault_mode == 4) g_return_size[0] = size + 65536u;
        g_return[0] = replacement;
        fprintf(stderr, "FAULT_INJECTION boundary=ucl_libucl mode=%u original=0x%x "
                        "replacement=0x%x bytes=%u\n",
                g_fault_mode, g_value[0], g_return[0], g_return_size[0]);
        fflush(stderr);
    }
#endif
    return ok;
}

unsigned char *interspec_ucl_value(uint32_t which)
{
    return which < 3 ? (unsigned char *)(uintptr_t)g_return[which] : NULL;
}

uint32_t interspec_ucl_value_size(uint32_t which)
{
    return which < 3 ? g_return_size[which] : 0;
}

void interspec_ucl_shutdown(void)
{
    clear_values();
    free(g_input);
    g_input = NULL;
    g_input_capacity = 0;
}
