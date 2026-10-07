#include "yaml.h"
#include "interspec_yaml_u_policy.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifndef INTERSPEC_YAML_TYPED_COPY
#define INTERSPEC_YAML_TYPED_COPY 0
#endif

#define INTERSPEC_YAML_STAGING_CAPACITY UINT32_C(8192)

static yaml_parser_t g_parser;
static yaml_event_t g_event;
static int g_parser_live;
static int g_event_live;

static unsigned char *g_input;
static uint32_t g_input_size;

static uint32_t g_staging;
static uint32_t g_wrong_type;
static uint32_t g_untracked;
static uint32_t g_alt_same_type;
static uint32_t g_return_ptr;
static uint32_t g_return_len;

static uint32_t g_fault_mode;
static int g_fault_used;

static uint32_t alloc_scalar_buffer(uint32_t bytes)
{
#if INTERSPEC_YAML_TYPED_COPY
    return INTERSPEC_SITE_SCALAR_VALUE_ALLOC(bytes);
#else
    unsigned char *ptr = (unsigned char *)malloc(bytes);
    return (uint32_t)(uintptr_t)ptr;
#endif
}

static void release_scalar_buffer(uint32_t ptr)
{
    if (!ptr)
        return;
#if INTERSPEC_YAML_TYPED_COPY
    (void)interspec_wasm_release(ptr);
#else
    free((void *)(uintptr_t)ptr);
#endif
}

static void clear_event(void)
{
    if (g_event_live) {
        yaml_event_delete(&g_event);
        g_event_live = 0;
    }
}

static void clear_fault_buffers(void)
{
#if INTERSPEC_YAML_TYPED_COPY
    if (g_wrong_type) {
        (void)interspec_wasm_release(g_wrong_type);
        g_wrong_type = 0;
    }
    if (g_alt_same_type) {
        (void)interspec_wasm_release(g_alt_same_type);
        g_alt_same_type = 0;
    }
#else
    g_wrong_type = 0;
    g_alt_same_type = 0;
#endif
    if (g_untracked) {
        free((void *)(uintptr_t)g_untracked);
        g_untracked = 0;
    }
}

unsigned char *interspec_yaml_setup(uint32_t input_size)
{
    if (g_parser_live || g_event_live)
        return NULL;

    if (g_input) {
        free(g_input);
        g_input = NULL;
    }
    clear_fault_buffers();
    release_scalar_buffer(g_staging);
    g_staging = 0;

    g_input = (unsigned char *)malloc(input_size ? input_size : 1);
    if (!g_input)
        return NULL;
    g_input_size = input_size;

    g_staging = alloc_scalar_buffer(INTERSPEC_YAML_STAGING_CAPACITY);
    if (!g_staging) {
        free(g_input);
        g_input = NULL;
        return NULL;
    }

    g_fault_mode = 0;
    g_fault_used = 0;
    return g_input;
}

void interspec_yaml_set_fault(uint32_t mode)
{
    g_fault_mode = mode;
    g_fault_used = 0;
}

int interspec_yaml_begin(void)
{
    clear_event();
    if (g_parser_live) {
        yaml_parser_delete(&g_parser);
        g_parser_live = 0;
    }

    if (!g_input || !yaml_parser_initialize(&g_parser))
        return 0;
    g_parser_live = 1;
    yaml_parser_set_input_string(&g_parser, g_input, g_input_size);
    g_return_ptr = 0;
    g_return_len = 0;
    return 1;
}

static int materialize_scalar(void)
{
    const uint32_t length = (uint32_t)g_event.data.scalar.length;
    if (!g_event.data.scalar.value ||
        length + 1 > INTERSPEC_YAML_STAGING_CAPACITY)
        return 0;

    memcpy((void *)(uintptr_t)g_staging,
           g_event.data.scalar.value, length);
    ((unsigned char *)(uintptr_t)g_staging)[length] = 0;
    g_return_ptr = g_staging;
    g_return_len = length;

#if INTERSPEC_YAML_TYPED_COPY
    if (!g_fault_used && g_fault_mode != 0) {
        g_fault_used = 1;

        if (g_fault_mode == 1) {
            if (!g_wrong_type)
                g_wrong_type = INTERSPEC_SITE_WRONG_TYPE_ALLOC(
                    INTERSPEC_YAML_STAGING_CAPACITY);
            if (!g_wrong_type)
                return 0;
            memcpy((void *)(uintptr_t)g_wrong_type,
                   g_event.data.scalar.value, length);
            g_return_ptr = g_wrong_type;
        } else if (g_fault_mode == 2) {
            if (!g_untracked)
                g_untracked = (uint32_t)(uintptr_t)
                    malloc(INTERSPEC_YAML_STAGING_CAPACITY);
            if (!g_untracked)
                return 0;
            memcpy((void *)(uintptr_t)g_untracked,
                   g_event.data.scalar.value, length);
            g_return_ptr = g_untracked;
        } else if (g_fault_mode == 3) {
            uint32_t stale = INTERSPEC_SITE_SCALAR_VALUE_ALLOC(
                INTERSPEC_YAML_STAGING_CAPACITY);
            if (!stale)
                return 0;
            memcpy((void *)(uintptr_t)stale,
                   g_event.data.scalar.value, length);
            if (!interspec_wasm_release(stale))
                return 0;
            g_return_ptr = stale;
        } else if (g_fault_mode == 4) {
            g_return_len = INTERSPEC_YAML_STAGING_CAPACITY + 1;
        } else if (g_fault_mode == 5) {
            if (!g_alt_same_type)
                g_alt_same_type = INTERSPEC_SITE_SCALAR_VALUE_ALLOC(
                    INTERSPEC_YAML_STAGING_CAPACITY);
            if (!g_alt_same_type)
                return 0;
            memcpy((void *)(uintptr_t)g_alt_same_type,
                   g_event.data.scalar.value, length);
            g_return_ptr = g_alt_same_type;
        }
    }
#endif
    return 1;
}

int interspec_yaml_next(void)
{
    clear_event();
    if (!g_parser_live)
        return 0;
    if (!yaml_parser_parse(&g_parser, &g_event))
        return -1;
    g_event_live = 1;
    g_return_ptr = 0;
    g_return_len = 0;

    if (g_event.type == YAML_SCALAR_EVENT &&
        !materialize_scalar())
        return -2;
    return 1;
}

uint32_t interspec_yaml_event_type(void)
{
    return g_event_live ? (uint32_t)g_event.type : 0;
}

unsigned char *interspec_yaml_scalar_pointer(void)
{
    return (unsigned char *)(uintptr_t)g_return_ptr;
}

uint32_t interspec_yaml_scalar_size(void)
{
    return g_return_len;
}

void interspec_yaml_end(void)
{
    clear_event();
    if (g_parser_live) {
        yaml_parser_delete(&g_parser);
        g_parser_live = 0;
    }
}

void interspec_yaml_shutdown(void)
{
    interspec_yaml_end();
    clear_fault_buffers();
    release_scalar_buffer(g_staging);
    g_staging = 0;
    if (g_input) {
        free(g_input);
        g_input = NULL;
    }
    g_input_size = 0;
    g_return_ptr = 0;
    g_return_len = 0;
}
