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
/* Two adversarial U pointer origins, compiled into the fault-only WASM module.
 * The trusted side must reject both before attempting to read their contents.
 * These do not represent the prevalence of such pointers in normal traffic. */
static unsigned char global_fault_probe[1u << 20];
static volatile uintptr_t escaped_stack_probe;
void interspec_mc_fault(uint32_t mode, uint32_t target) {
    fault_mode = mode;
    fault_target = target;
}
/* Policy-switch tests (tracker item I2), same flag bits as the rsync/popt PoC:
 * 1 = U reads the value it was handed for the peek_all length out-parameter,
 * 2 = U overwrites its copy of the data passed to offer. */
static uint32_t poc_flags;
void interspec_mc_poc(uint32_t flags) { poc_flags = flags; }
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
    /* Modes 101..110 are matched-content controls: U alters the legitimate
     * owner bytes/length but does not replace the return pointer. The T copy
     * digest lets the independent verifier confirm actual byte equivalence. */
    const int content_control = fault_mode >= 101 && fault_mode <= 110;
    const uint32_t scenario = content_control ? fault_mode - 100 : fault_mode;
    switch (scenario) {
    case 1:
        if (content_control) memcpy(ptr, input, last_size);
        else ptr = input; /* Live char allocation, wrong expected type. */
        break;
    case 2:
        if (!content_control) {
            unsigned char *other = malloc(capacity);
            if (!other || last_size > capacity) abort();
            memcpy(other, ptr, last_size);
            ptr = other; /* Untracked U heap with identical T-visible bytes. */
        }
        break;
    case 3:
        if (content_control) break;
#if INTERSPEC_TRACKING
        interspec_wasm_release((uint32_t)(uintptr_t)owner);
#else
        /* The RLBox-only comparator has no InterSpec allocation metadata.
         * Releasing the ordinary U allocation models the same stale origin. */
        free(owner);
#endif
        break; /* Stale owner metadata; do not read this pointer afterwards. */
    case 4:
        if (target == 2) last_size = capacity + 1;
        else if (!content_control) ptr = owner->data + capacity - 1;
        break;
    case 5: { /* Same-type substitution is an explicit accepted scope control. */
        bipbuf_t *replacement = bipbuf_new(capacity);
        if (!replacement) abort();
        memcpy(replacement->data, ptr, last_size);
        if (!content_control) ptr = replacement->data;
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
    case 9:
        if (last_size > sizeof(global_fault_probe)) abort();
        if (content_control) memcpy(ptr, global_fault_probe, last_size);
        else ptr = global_fault_probe; /* Untracked U static-duration object. */
        break;
    case 10: {
        /* Deliberately escape a U stack address as an integer. No T
         * dereference is permitted; this is a rejected-lifetime probe. */
        volatile unsigned char stack_fault_probe[64] = {0};
        escaped_stack_probe = (uintptr_t)&stack_fault_probe[0];
        if (content_control) memset(ptr, 0, last_size);
        else ptr = (unsigned char *)(uintptr_t)escaped_stack_probe;
        break;
    }
    case 11: { /* H2: retain the T domain but forge an interior item*. */
        if (target != 2 || last_size < sizeof(uint64_t)) abort();
        uint64_t address;
        memcpy(&address, ptr, sizeof(address));
        ++address;
        memcpy(ptr, &address, sizeof(address));
        break;
    }
    case 12: { /* H2: forge a T-domain address outside the queued object. */
        if (target != 2 || last_size < sizeof(uint64_t)) abort();
        uint64_t address;
        memcpy(&address, ptr, sizeof(address));
        address += 65536u;
        memcpy(ptr, &address, sizeof(address));
        break;
    }
    default: abort();
    }
    fprintf(stderr, "FAULT_INJECTION boundary=memcached_bipbuffer mode=%u target=%u control=%u original=0x%x replacement=0x%x bytes=%u\n",
            fault_mode, target, (unsigned)content_control,
            (unsigned)(uintptr_t)original, (unsigned)(uintptr_t)ptr, last_size);
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
int interspec_mc_offer(uint32_t size) {
    int written = bipbuf_offer(owner, input, (int)size);
#ifdef INTERSPEC_FAULT_TESTS
    if ((poc_flags & 2u) && size) {
        const unsigned old = input[0];
        input[0] ^= 0xff;
        fprintf(stderr, "[InterSpec][PoC][SP2] sandbox mutated offer data byte=0 old=0x%02x new=0x%02x\n",
                old, (unsigned)input[0]);
        fflush(stderr);
    }
#endif
    return written;
}
/* len_in is what the wrapper copies in for the length out-parameter. Upstream
 * bipbuf_peek_all only writes *len, so with SP1 on the wrapper passes 0 and
 * T's value never enters U. With SP1 off it passes T's value. */
unsigned char *interspec_mc_peek_all(uint32_t len_in) {
    last_size = len_in;
#ifdef INTERSPEC_FAULT_TESTS
    if (poc_flags & 1u) {
        fprintf(stderr, "[InterSpec][PoC][SP1] sandbox read peek_all len_in=0x%x\n", last_size);
        fflush(stderr);
    }
#endif
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
