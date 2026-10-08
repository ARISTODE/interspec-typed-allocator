#include "pcre.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#if INTERSPEC_TRACKING
#include "interspec_pcre_u_policy.h"
#endif

/* One compiled expression per sandbox. No native nginx pointer enters U. */
#define INPUT_CAPACITY 65536u
#define OFFSET_CAPACITY 4096u
static pcre *code;
static pcre_extra *study;
static unsigned char *input;
static int *offsets;
static unsigned char *names;
static uint32_t names_bytes, offsets_bytes;
static int capture_count, name_count, entry_size;
#ifdef INTERSPEC_FAULT_TESTS
static uint32_t fault_path, fault_kind;
void interspec_nginx_fault(uint32_t path, uint32_t kind)
{ fault_path = path; fault_kind = kind; }
#endif

unsigned char *interspec_nginx_setup(void)
{
#if INTERSPEC_TRACKING
    input = (void *)(uintptr_t)INTERSPEC_SITE_SUBJECT_INPUT_ALLOC(INPUT_CAPACITY);
    offsets = (void *)(uintptr_t)INTERSPEC_SITE_CAPTURE_OFFSETS_ALLOC(OFFSET_CAPACITY * sizeof(int));
#else
    input = malloc(INPUT_CAPACITY);
    offsets = malloc(OFFSET_CAPACITY * sizeof(int));
#endif
    return input && offsets ? input : NULL;
}

int interspec_nginx_compile(int options)
{
    const char *error = NULL;
    int error_offset = 0;
    code = pcre_compile((const char *)input, options, &error, &error_offset, NULL);
    if (!code) return 0;
    if (pcre_fullinfo(code, NULL, PCRE_INFO_CAPTURECOUNT, &capture_count) ||
        pcre_fullinfo(code, NULL, PCRE_INFO_NAMECOUNT, &name_count) ||
        pcre_fullinfo(code, NULL, PCRE_INFO_NAMEENTRYSIZE, &entry_size) ||
        pcre_fullinfo(code, NULL, PCRE_INFO_NAMETABLE, &names)) return 0;
    names_bytes = (uint32_t)name_count * (uint32_t)entry_size;
    return 1;
}

int interspec_nginx_info(int what)
{
    if (what == PCRE_INFO_CAPTURECOUNT) return capture_count;
    if (what == PCRE_INFO_NAMECOUNT) return name_count;
    if (what == PCRE_INFO_NAMEENTRYSIZE) return entry_size;
    return -1;
}

int interspec_nginx_study(void)
{
    const char *error = NULL;
    study = pcre_study(code, 0, &error);
    return error == NULL;
}

#ifdef INTERSPEC_FAULT_TESTS
static void *corrupt(void *original, uint32_t bytes, uint32_t path)
{
    void *p = original;
    if (fault_path != path || !fault_kind) return p;
    if (fault_kind == 1) {
        /* A live allocation of the wrong expected type. */
        p = (void *)(uintptr_t)INTERSPEC_SITE_SUBJECT_INPUT_ALLOC(bytes);
    } else if (fault_kind == 2) {
        p = malloc(bytes);
    } else if (fault_kind == 3 || fault_kind == 5) {
        p = (void *)(uintptr_t)(path == 1 ? INTERSPEC_SITE_COMPILED_REGEX_ALLOC(bytes) :
                                                   INTERSPEC_SITE_CAPTURE_OFFSETS_ALLOC(bytes));
    }
    if (p && p != original) memcpy(p, original, bytes);
    if (fault_kind == 3 && p) interspec_wasm_release((uint32_t)(uintptr_t)p);
    return p;
}
#endif

unsigned char *interspec_nginx_names(void)
{
#ifdef INTERSPEC_FAULT_TESTS
    return corrupt(names, names_bytes, 1);
#else
    return names;
#endif
}
uint32_t interspec_nginx_names_bytes(void)
{
#ifdef INTERSPEC_FAULT_TESTS
    if (fault_path == 1 && fault_kind == 4) return names_bytes + 262144;
#endif
    return names_bytes;
}

int interspec_nginx_exec(int length, int start, int options, int count)
{
    if (length < 0 || length > (int)INPUT_CAPACITY || count < 0 || count > (int)OFFSET_CAPACITY)
        return PCRE_ERROR_BADLENGTH;
    for (int i = 0; i < count; ++i) offsets[i] = -1;
    offsets_bytes = (uint32_t)count * sizeof(int);
    return pcre_exec(code, study, (const char *)input, length, start, options, offsets, count);
}
unsigned char *interspec_nginx_offsets(void)
{
#ifdef INTERSPEC_FAULT_TESTS
    if (fault_path == 2 && fault_kind == 6 && offsets_bytes >= 8) offsets[1] = INT32_MAX;
    return corrupt(offsets, offsets_bytes, 2);
#else
    return (unsigned char *)offsets;
#endif
}
uint32_t interspec_nginx_offsets_bytes(void)
{
#ifdef INTERSPEC_FAULT_TESTS
    if (fault_path == 2 && fault_kind == 4) return offsets_bytes + 262144;
#endif
    return offsets_bytes;
}
