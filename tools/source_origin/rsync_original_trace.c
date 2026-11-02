/* Diagnostic native intercepts of two original rsync API calls.
 * poptBadOption belongs to the isolated interface in the deployed bridge.
 * poptStrerror is an explicitly trusted-host helper in that bridge.
 * The diagnostic code is never included in the original-source census.
 */
#define _GNU_SOURCE
#include "popt.h"
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
static int lookup_elf(struct dl_phdr_info *info, size_t ignored, void *arg) {
    (void)ignored;
    struct lookup *q = (struct lookup *)arg;
    for (int i = 0; i < info->dlpi_phnum; ++i) {
        const ElfW(Phdr) *p = &info->dlpi_phdr[i];
        if (p->p_type != PT_LOAD || !(p->p_flags & PF_R) ||
            (p->p_flags & PF_X)) continue;
        uintptr_t base = (uintptr_t)info->dlpi_addr;
        uintptr_t offset = (uintptr_t)p->p_vaddr;
        if (offset > UINTPTR_MAX - base) continue;
        uintptr_t start = base + offset;
        if (q->address >= start && q->address - start < (uintptr_t)p->p_memsz) {
            q->origin = (p->p_flags & PF_W)
                ? "native_writable_image_candidate" : "native_readonly_image_candidate";
            return 1;
        }
    }
    return 0;
}
static const char *classify(const void *pointer) {
    if (!pointer) return "null";
    uintptr_t address = (uintptr_t)pointer;
    pthread_attr_t attr;
    if (pthread_getattr_np(pthread_self(), &attr) == 0) {
        void *base = NULL;
        size_t size = 0;
        int valid = pthread_attr_getstack(&attr, &base, &size) == 0;
        pthread_attr_destroy(&attr);
        if (valid && address >= (uintptr_t)base &&
            address - (uintptr_t)base < size)
            return "native_process_stack";
    }
    struct lookup q = {address, "unresolved_mapping"};
    dl_iterate_phdr(lookup_elf, &q);
    return q.origin;
}
static void record(const char *api, const char *role,
                   const void *pointer, uintptr_t caller) {
    const char *path = getenv("INTERSPEC_RSYNC_ORIGINAL_TRACE");
    if (!path || !*path) return;
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0600);
    if (fd < 0) return;
    char line[360];
    int n = snprintf(line, sizeof(line),
        "{\"schema\":2,\"api\":\"%s\",\"role\":\"%s\",\"origin\":\"%s\","
        "\"caller_pc\":\"0x%zx\",\"address\":\"0x%zx\"}\n",
        api, role, classify(pointer), (size_t)caller, (size_t)(uintptr_t)pointer);
    if (n > 0 && (size_t)n < sizeof(line))
        (void)write(fd, line, (size_t)n);
    close(fd);
}

extern const char *__real_poptBadOption(poptContext, unsigned int);
__attribute__((noinline))
const char *__wrap_poptBadOption(poptContext context, unsigned int flags) {
    uintptr_t caller = (uintptr_t)__builtin_return_address(0);
    record("poptBadOption", "t_to_u_context_pointer", context, caller);
    const char *result = __real_poptBadOption(context, flags);
    record("poptBadOption", "u_to_t_bad_option_pointer", result, caller);
    return result;
}

extern const char *__real_poptStrerror(const int);
__attribute__((noinline))
const char *__wrap_poptStrerror(const int error) {
    uintptr_t caller = (uintptr_t)__builtin_return_address(0);
    const char *result = __real_poptStrerror(error);
    record("poptStrerror", "host_helper_error_pointer_not_isolated", result, caller);
    return result;
}
