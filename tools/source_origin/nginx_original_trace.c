/* Diagnostic interception of upstream Nginx PCRE API calls.
 * The Nginx and PCRE C files are unmodified; this diagnostic is not counted.
 */
#define _GNU_SOURCE
#include "pcre.h"
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <pthread.h>
#include <link.h>
#include <limits.h>

struct lookup { uintptr_t address; const char *origin; };
static int classify_segment(struct dl_phdr_info *info, size_t unused, void *arg) {
    (void)unused;
    struct lookup *q = (struct lookup *)arg;
    for (int i = 0; i < info->dlpi_phnum; ++i) {
        const ElfW(Phdr) *p = &info->dlpi_phdr[i];
        if (p->p_type != PT_LOAD || !(p->p_flags & PF_R) ||
            (p->p_flags & PF_X)) continue;
        uintptr_t b = (uintptr_t)info->dlpi_addr, offset = (uintptr_t)p->p_vaddr;
        if (offset > UINTPTR_MAX - b) continue;
        uintptr_t start = b + offset;
        if (q->address >= start && q->address - start < (uintptr_t)p->p_memsz) {
            q->origin = (p->p_flags & PF_W)
                ? "writable_elf_image_candidate" : "readonly_elf_image_candidate";
            return 1;
        }
    }
    return 0;
}
static const char *classify_pointer(const void *ptr) {
    if (!ptr) return "null";
    uintptr_t v = (uintptr_t)ptr;
    pthread_attr_t attr;
    if (pthread_getattr_np(pthread_self(), &attr) == 0) {
        void *start = NULL;
        size_t bytes = 0;
        int valid = pthread_attr_getstack(&attr, &start, &bytes) == 0;
        pthread_attr_destroy(&attr);
        if (valid && v >= (uintptr_t)start && v - (uintptr_t)start < bytes)
            return "stack";
    }
    struct lookup q = {v, "unresolved_mapping"};
    dl_iterate_phdr(classify_segment, &q);
    return q.origin;
}
static void record(const char *api, const char *role, const void *ptr,
                   uintptr_t caller) {
    const char *path = getenv("INTERSPEC_NGINX_ORIGINAL_TRACE");
    if (!path || !*path) return;
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0600);
    if (fd < 0) return;
    char line[320];
    int n = snprintf(line, sizeof(line),
        "{\"schema\":1,\"api\":\"%s\",\"role\":\"%s\",\"origin\":\"%s\","
        "\"caller_pc\":\"0x%zx\",\"address\":\"0x%zx\"}\n",
        api, role, classify_pointer(ptr), (size_t)caller, (size_t)(uintptr_t)ptr);
    if (n > 0 && (size_t)n < sizeof(line))
        (void)write(fd, line, (size_t)n);
    close(fd);
}

extern pcre *__real_pcre_compile(const char *, int, const char **,
                                int *, const unsigned char *);
__attribute__((noinline))
pcre *__wrap_pcre_compile(const char *pattern, int options,
                          const char **errorptr, int *erroffset,
                          const unsigned char *tableptr) {
    uintptr_t caller = (uintptr_t)__builtin_return_address(0);
    record("pcre_compile", "t_to_u_pattern", pattern, caller);
    record("pcre_compile", "t_to_u_errorptr_outparam", errorptr, caller);
    record("pcre_compile", "t_to_u_erroffset_outparam", erroffset, caller);
    record("pcre_compile", "t_to_u_tableptr", tableptr, caller);
    pcre *result = __real_pcre_compile(pattern, options, errorptr, erroffset, tableptr);
    record("pcre_compile", "u_to_t_compiled_regex", result, caller);
    if (errorptr && *errorptr)
        record("pcre_compile", "u_to_t_error_string", *errorptr, caller);
    return result;
}
extern pcre_extra *__real_pcre_study(const pcre *, int, const char **);
__attribute__((noinline))
pcre_extra *__wrap_pcre_study(const pcre *code, int options,
                             const char **errorptr) {
    uintptr_t caller = (uintptr_t)__builtin_return_address(0);
    record("pcre_study", "t_to_u_regex", code, caller);
    record("pcre_study", "t_to_u_errorptr_outparam", errorptr, caller);
    pcre_extra *result = __real_pcre_study(code, options, errorptr);
    record("pcre_study", "u_to_t_study_result", result, caller);
    if (errorptr && *errorptr)
        record("pcre_study", "u_to_t_error_string", *errorptr, caller);
    return result;
}
