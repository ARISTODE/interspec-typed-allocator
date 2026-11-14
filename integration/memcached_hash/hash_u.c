/* Compiled into U together with the hash function of the interspec-artifact
 * wrapper (hash_untrusted.c, unchanged), which is all that the artifact
 * isolates at the memcached/hash boundary. Adds staging memory for the key
 * and a wrapper that takes its address as a 32-bit value. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

uint64_t hash_untrusted(const char *data, uint32_t len);

static unsigned char *g_key;
static uint32_t g_key_capacity;

#ifdef INTERSPEC_FAULT_TESTS
static uint32_t g_poc_flags;
/* Policy-switch test, same flag bit as the other boundaries:
 * 2 = U overwrites its copy of the key after hashing it. */
void interspec_hash_poc(uint32_t flags) { g_poc_flags = flags; }
#endif

unsigned char *interspec_hash_stage(uint32_t bytes)
{
    if (bytes > g_key_capacity) {
        free(g_key);
        g_key = calloc(1, bytes);
        g_key_capacity = g_key ? bytes : 0;
    }
    return g_key;
}

/* unsigned long long: RLBox maps types by name, and long is 32 bits wide
 * inside the sandbox. */
unsigned long long interspec_hash_run(uint32_t key_addr, uint32_t len)
{
    const unsigned long long value = hash_untrusted((const char *)(uintptr_t)key_addr, len);
#ifdef INTERSPEC_FAULT_TESTS
    if ((g_poc_flags & 2u) && len) {
        unsigned char *key = (unsigned char *)(uintptr_t)key_addr;
        const unsigned old = key[0];
        key[0] ^= 0xff;
        fprintf(stderr, "[InterSpec][PoC][SP2] sandbox mutated key byte=0 "
                        "old=0x%02x new=0x%02x\n", old, (unsigned)key[0]);
        fflush(stderr);
        g_poc_flags &= ~2u; /* once */
    }
#endif
    return value;
}
