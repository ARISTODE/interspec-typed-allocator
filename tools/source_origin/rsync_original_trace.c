/* Instrument original rsync application calls to vendored poptStrerror.
 * Do not count any code from this diagnostic file as an original source site.
 * No original application or library source file is modified.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <link.h>
#include <limits.h>

struct pointer_lookup { uintptr_t address; const char *origin; };

static int classify_segment(struct dl_phdr_info *info, size_t unused, void *arg) {
    (void)unused;
    struct pointer_lookup *q = (struct pointer_lookup *)arg;
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
                ? "writable_elf_image_candidate" : "readonly_elf_image_candidate";
            return 1;
        }
    }
    return 0;
}

static const char *classify_error_result(const char *pointer) {
    if (pointer == NULL) return "null";
    struct pointer_lookup q = {(uintptr_t)pointer, "unresolved_mapping"};
    dl_iterate_phdr(classify_segment, &q);
    return q.origin;
}

extern const char *__real_poptStrerror(const int);
__attribute__((noinline))
const char *__wrap_poptStrerror(const int error) {
    uintptr_t caller_pc = (uintptr_t)__builtin_return_address(0);
    const char *result = __real_poptStrerror(error);
    const char *path = getenv("INTERSPEC_RSYNC_ORIGINAL_TRACE");
    if (path && *path) {
        int fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0600);
        if (fd >= 0) {
            char line[320];
            int n = snprintf(line, sizeof(line),
                "{\"schema\":1,\"api\":\"poptStrerror\","
                "\"role\":\"u_to_t_error_string\","
                "\"origin\":\"%s\",\"error_code\":%d,"
                "\"caller_pc\":\"0x%zx\",\"address\":\"0x%zx\"}\n",
                classify_error_result(result), error, (size_t)caller_pc,
                (size_t)(uintptr_t)result);
            if (n > 0 && (size_t)n < sizeof(line))
                (void)write(fd, line, (size_t)n);
            close(fd);
        }
    }
    return result;
}
