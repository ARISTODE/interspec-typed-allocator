/* Diagnostic linker interception of unchanged upstream memcached C calls.
 * The wrapper implementation is NEVER included in pointer-origin counts.
 * Only calls made by original logger.c/items.c are accepted by the verifier.
 */
#define _GNU_SOURCE
#include "bipbuffer.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <pthread.h>
#include <link.h>
#include <limits.h>

static pthread_once_t trace_once = PTHREAD_ONCE_INIT;
static int trace_fd = -1;

static void initialize_trace(void) {
    const char *path = getenv("INTERSPEC_ORIGINAL_SOURCE_TRACE");
    if (path && path[0]) {
        trace_fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0600);
    }
}

struct lookup { uintptr_t address; const char *origin; };
static int lookup_elf(struct dl_phdr_info *info, size_t ignored, void *arg) {
    (void) ignored;
    struct lookup *q = (struct lookup *)arg;
    for (int i = 0; i < info->dlpi_phnum; ++i) {
        const ElfW(Phdr) *segment = &info->dlpi_phdr[i];
        if (segment->p_type != PT_LOAD || !(segment->p_flags & PF_R) ||
            (segment->p_flags & PF_X)) continue;
        uintptr_t base = (uintptr_t)info->dlpi_addr;
        uintptr_t offset = (uintptr_t)segment->p_vaddr;
        if (offset > UINTPTR_MAX - base) continue;
        uintptr_t start = base + offset;
        if (q->address >= start &&
            q->address - start < (uintptr_t)segment->p_memsz) {
            q->origin = (segment->p_flags & PF_W) ?
                "t_image_writable_candidate" : "t_image_readonly_candidate";
            return 1;
        }
    }
    return 0;
}

static const char *classify_host(const void *ptr) {
    if (!ptr) return "null";
    uintptr_t address = (uintptr_t)ptr;
    pthread_attr_t attr;
    if (pthread_getattr_np(pthread_self(), &attr) == 0) {
        void *base = NULL;
        size_t size = 0;
        int ok = pthread_attr_getstack(&attr, &base, &size) == 0;
        pthread_attr_destroy(&attr);
        if (ok && address >= (uintptr_t)base &&
            address - (uintptr_t)base < size) return "t_stack";
    }
    struct lookup q = {address, "unknown"};
    dl_iterate_phdr(lookup_elf, &q);
    return q.origin;
}

static const char *classify_interior(const bipbuf_t *buf, const void *ptr) {
    if (!ptr) return "null";
    if (!buf) return "unknown";
    uintptr_t base = (uintptr_t)buf->data;
    uintptr_t value = (uintptr_t)ptr;
    if (value >= base && value - base < buf->size)
        return "u_heap_interior";
    return "unknown";
}

static void record(const char *api, const char *role, const char *origin,
                   const void *address, uintptr_t caller, size_t bytes) {
    pthread_once(&trace_once, initialize_trace);
    if (trace_fd < 0) return;
    char line[384];
    int n = snprintf(line, sizeof(line),
        "{\"schema\":1,\"api\":\"%s\",\"role\":\"%s\",\"origin\":\"%s\","
        "\"caller_pc\":\"0x%zx\",\"address\":\"0x%zx\",\"bytes\":%zu}\n",
        api, role, origin, (size_t)caller, (size_t)(uintptr_t)address, bytes);
    if (n > 0 && (size_t)n < sizeof(line)) {
        (void)write(trace_fd, line, (size_t)n);
    }
}

extern int __real_bipbuf_offer(bipbuf_t *, const unsigned char *, int);
__attribute__((noinline))
int __wrap_bipbuf_offer(bipbuf_t *buf, const unsigned char *data, int size) {
    uintptr_t caller = (uintptr_t)__builtin_return_address(0);
    record("bipbuf_offer", "t_to_u_data", classify_host(data),
           data, caller, size >= 0 ? (size_t)size : 0);
    return __real_bipbuf_offer(buf, data, size);
}

extern unsigned char *__real_bipbuf_peek_all(const bipbuf_t *, unsigned int *);
__attribute__((noinline))
unsigned char *__wrap_bipbuf_peek_all(const bipbuf_t *buf, unsigned int *size) {
    uintptr_t caller = (uintptr_t)__builtin_return_address(0);
    record("bipbuf_peek_all", "t_to_u_outparam", classify_host(size),
           size, caller, sizeof(unsigned int));
    unsigned char *result = __real_bipbuf_peek_all(buf, size);
    record("bipbuf_peek_all", "u_to_t_return", classify_interior(buf, result),
           result, caller, result && size ? *size : 0);
    return result;
}

extern unsigned char *__real_bipbuf_request(bipbuf_t *, int);
__attribute__((noinline))
unsigned char *__wrap_bipbuf_request(bipbuf_t *buf, int size) {
    uintptr_t caller = (uintptr_t)__builtin_return_address(0);
    unsigned char *result = __real_bipbuf_request(buf, size);
    record("bipbuf_request", "u_to_t_return", classify_interior(buf, result),
           result, caller, size >= 0 ? (size_t)size : 0);
    return result;
}

extern unsigned char *__real_bipbuf_poll(bipbuf_t *, unsigned int);
__attribute__((noinline))
unsigned char *__wrap_bipbuf_poll(bipbuf_t *buf, unsigned int size) {
    uintptr_t caller = (uintptr_t)__builtin_return_address(0);
    unsigned char *result = __real_bipbuf_poll(buf, size);
    record("bipbuf_poll", "u_to_t_return", classify_interior(buf, result),
           result, caller, size);
    return result;
}
