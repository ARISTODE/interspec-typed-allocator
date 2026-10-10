/* Compiled into U. Each sandbox contains one actual upstream bipbuffer. */
#include "bipbuffer.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if INTERSPEC_TRACKING
#include "interspec_bipbuffer_u_policy.h"
#endif

static bipbuf_t *owner;
static unsigned char *input;
static uint32_t capacity, last_size;
#ifdef INTERSPEC_BOUNDARY_BENCH
/* Exported only by the separate measurement module, never the server module. */
uint32_t interspec_mc_bench_noop(uint32_t value) { return value + 1; }
#endif
#ifdef INTERSPEC_FAULT_TESTS
static uint32_t fault_mode, fault_target, fault_fired;
void interspec_mc_fault(uint32_t mode, uint32_t target) {
    fault_mode = mode;
    fault_target = target;
}
#endif

unsigned char *interspec_mc_new(uint32_t size) {
    capacity = size;
    owner = bipbuf_new(size);
#if INTERSPEC_TRACKING
    input = (void *)(uintptr_t)INTERSPEC_SITE_INPUT_COPY_ALLOC(size);
#else
    input = malloc(size);
#endif
    return owner && input ? input : NULL;
}

static unsigned char *mutate(unsigned char *ptr, uint32_t target) {
#ifdef INTERSPEC_FAULT_TESTS
    if (!ptr || fault_fired || !fault_mode || target != fault_target) return ptr;
    fault_fired = 1;
    unsigned char *original = ptr;
    switch (fault_mode) {
    case 1: ptr = input; break; /* Live tracked char allocation, wrong type. */
    case 2: ptr = malloc(capacity); break; /* Ordinary untracked U storage. */
    case 3:
        interspec_wasm_release((uint32_t)(uintptr_t)owner);
        break; /* Stale owner metadata; do not read this pointer afterwards. */
    case 4:
        if (target == 2) last_size = capacity + 1;
        else ptr = owner->data + capacity - 1;
        break;
    case 5: { /* Same-type substitution is an explicit accepted scope control. */
        bipbuf_t *replacement = bipbuf_new(capacity);
        if (!replacement) abort();
        memcpy(replacement->data, ptr, last_size);
        ptr = replacement->data;
        break;
    }
    case 6: /* Malformed record contents: handled by T's format validator. */
        memset(ptr, 0xff, last_size < 4 ? last_size : 4);
        break;
    case 7: /* Corrupt the hash next to an opaque 64-bit LRU handle. */
        if (last_size >= 12) ptr[8] ^= 1;
        break;
    case 8: /* A tracked, in-bounds extent that splits an LRU record. */
        if (last_size) --last_size;
        break;
    default: abort();
    }
    fprintf(stderr, "FAULT_INJECTION boundary=memcached_bipbuffer mode=%u target=%u original=0x%x replacement=0x%x bytes=%u\n",
            fault_mode, target, (unsigned)(uintptr_t)original,
            (unsigned)(uintptr_t)ptr, last_size);
    fflush(stderr);
#else
    (void)target;
#endif
    return ptr;
}

unsigned char *interspec_mc_request(uint32_t size) {
    last_size = size;
    return mutate(bipbuf_request(owner, (int)size), 1);
}
int interspec_mc_push(uint32_t size) { return bipbuf_push(owner, (int)size); }
int interspec_mc_offer(uint32_t size) { return bipbuf_offer(owner, input, (int)size); }
unsigned char *interspec_mc_peek_all(void) {
    last_size = 0;
    unsigned char *ptr = bipbuf_peek_all(owner, &last_size);
    return mutate(ptr, 2);
}
unsigned char *interspec_mc_peek(uint32_t size) {
    last_size = size;
    return mutate(bipbuf_peek(owner, size), 4);
}
unsigned char *interspec_mc_poll(uint32_t size) {
    last_size = size;
    return mutate(bipbuf_poll(owner, size), 3);
}
uint32_t interspec_mc_last_size(void) { return last_size; }
int interspec_mc_used(void) { return bipbuf_used(owner); }
int interspec_mc_unused(void) { return bipbuf_unused(owner); }
int interspec_mc_empty(void) { return bipbuf_is_empty(owner); }
void interspec_mc_reset(uint32_t size) { bipbuf_init(owner, size); }
void interspec_mc_free(void) {
    bipbuf_free(owner);
#if INTERSPEC_TRACKING
    interspec_wasm_release((uint32_t)(uintptr_t)input);
#else
    free(input);
#endif
}
