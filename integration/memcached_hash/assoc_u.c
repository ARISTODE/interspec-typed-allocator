/* memcached's hash table inside U (tracker item I9). The functions follow
 * assoc.c of memcached at the pinned revision: the same bucket array, the same
 * chaining through h_next, the same find, insert, delete and iterator logic.
 * Differences, all forced by running without access to T's memory:
 *   - an entry is U's copy of the item image (assoc_bridge.h), not T's item;
 *     it carries the handle that names T's item;
 *   - the table has a fixed size (no expansion thread), and the iterator takes
 *     no bucket locks: the port is single-threaded.
 *
 * Handles and addresses are uintptr_t: 32 bits inside the sandbox, where T
 * passes them as 32-bit values, and pointer-sized in the native reference. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "assoc_bridge.h"

typedef struct assoc_entry_s {
    struct assoc_entry_s *h_next;
    uintptr_t item;              /* T's handle for its item */
    uint32_t bytes;              /* size of the image that follows */
    assoc_item_image_t image;    /* header, then key, then value if copied in */
} assoc_entry_t;

#define hashsize(n) ((uint64_t)1 << (n))
#define hashmask(n) (hashsize(n) - 1)

static unsigned int hashpower = 16;
static assoc_entry_t **primary_hashtable;

#ifdef INTERSPEC_FAULT_TESTS
static uint32_t g_fault_mode, g_fault_used, g_poc_flags;
static assoc_entry_t *g_kept;    /* an entry U was told to delete and kept */
/* What a compromised U does: 1 = the next find returns a value T never issued,
 * 2 = the next delete keeps the entry, and a later find of that key returns
 * its old handle, 3 = the next find returns the handle of another live item. */
void interspec_assoc_fault(uint32_t mode) { g_fault_mode = mode; g_fault_used = 0; }
/* Policy-switch tests, same flag bits as the other boundaries:
 * 1 = U reads the item fields and value bytes that assoc does not need,
 * 2 = U overwrites fields of its copy of the item that assoc does not write. */
void interspec_assoc_poc(uint32_t flags) { g_poc_flags = flags; }
#endif

int interspec_assoc_init(uint32_t hashpower_init)
{
    if (hashpower_init) hashpower = hashpower_init;
    if (hashpower > 24) return 0;
    primary_hashtable = calloc(hashsize(hashpower), sizeof(void *));
    return primary_hashtable != NULL;
}

/* assoc_find. Returns the handle of T's item, or 0. */
uintptr_t interspec_assoc_find(const char *key, uint32_t nkey, uint32_t hv)
{
    assoc_entry_t *it = primary_hashtable[hv & hashmask(hashpower)];
    uintptr_t ret = 0;
    while (it) {
        if ((nkey == it->image.nkey) && (memcmp(key, ASSOC_IMAGE_KEY(&it->image), nkey) == 0)) {
            ret = it->item;
            break;
        }
        it = it->h_next;
    }
#ifdef INTERSPEC_FAULT_TESTS
    if (g_fault_mode == 2 && !ret && g_kept && nkey == g_kept->image.nkey &&
        memcmp(key, ASSOC_IMAGE_KEY(&g_kept->image), nkey) == 0) {
        ret = g_kept->item;
        fprintf(stderr, "FAULT_INJECTION boundary=memcached_hash mode=2 stale_handle=0x%x\n",
                (unsigned)ret);
        fflush(stderr);
    } else if ((g_fault_mode == 1 || g_fault_mode == 3) && !g_fault_used && ret) {
        uintptr_t replacement = 0x5ec2e7f0u;
        if (g_fault_mode == 3) {
            replacement = 0;
            for (uint64_t b = 0; b < hashsize(hashpower) && !replacement; ++b)
                for (assoc_entry_t *e = primary_hashtable[b]; e; e = e->h_next)
                    if (e->item != ret) { replacement = e->item; break; }
        }
        if (replacement) {
            g_fault_used = 1;
            fprintf(stderr, "FAULT_INJECTION boundary=memcached_hash mode=%u original=0x%x "
                            "replacement=0x%x\n",
                    g_fault_mode, (unsigned)ret, (unsigned)replacement);
            fflush(stderr);
            ret = replacement;
        }
    }
#endif
    return ret;
}

static assoc_entry_t **hashitem_before(const char *key, uint32_t nkey, uint32_t hv)
{
    assoc_entry_t **pos = &primary_hashtable[hv & hashmask(hashpower)];
    while (*pos && ((nkey != (*pos)->image.nkey) ||
                    memcmp(key, ASSOC_IMAGE_KEY(&(*pos)->image), nkey))) {
        pos = &(*pos)->h_next;
    }
    return pos;
}

/* assoc_insert. `image` is the wrapper's copy of T's item (`bytes` long);
 * `item` is the handle T issued for it. The key must not be in the table. */
int interspec_assoc_insert(assoc_item_image_t *image, uint32_t bytes, uintptr_t item,
                           uint32_t hv)
{
    if (bytes < sizeof(*image) || bytes - sizeof(*image) < image->nkey) return 0;
#ifdef INTERSPEC_FAULT_TESTS
    if (g_poc_flags & 1u) {
        const unsigned char *value = (const unsigned char *)ASSOC_IMAGE_VALUE(image);
        const uint32_t have = bytes - (uint32_t)sizeof(*image) - image->nkey;
        fprintf(stderr, "[InterSpec][PoC][SP1] sandbox read item exptime=0x%x nbytes=%d "
                        "value_bytes_received=%u value_first4=%02x%02x%02x%02x\n",
                image->exptime, image->nbytes, have, have > 0 ? value[0] : 0,
                have > 1 ? value[1] : 0, have > 2 ? value[2] : 0, have > 3 ? value[3] : 0);
        fflush(stderr);
        g_poc_flags &= ~1u; /* once */
    }
#endif
    assoc_entry_t *entry = malloc(sizeof(*entry) - sizeof(entry->image) + bytes);
    if (!entry) return 0;
    memcpy(&entry->image, image, bytes);
    entry->bytes = bytes;
    entry->item = item;
    entry->h_next = primary_hashtable[hv & hashmask(hashpower)];
    primary_hashtable[hv & hashmask(hashpower)] = entry;
    /* The field assoc.c writes in the item: the chain link. */
    image->h_next = (uint32_t)(uintptr_t)entry->h_next;
#ifdef INTERSPEC_FAULT_TESTS
    if (g_poc_flags & 2u) {
        image->refcount = 0xffff;
        ASSOC_IMAGE_KEY(image)[0] ^= 0xff;
        fprintf(stderr, "[InterSpec][PoC][SP2] sandbox mutated item refcount=0xffff "
                        "key_byte0=0x%02x\n", (unsigned char)ASSOC_IMAGE_KEY(image)[0]);
        fflush(stderr);
        g_poc_flags &= ~2u; /* once */
    }
#endif
    return 1;
}

/* assoc_delete. */
void interspec_assoc_delete(const char *key, uint32_t nkey, uint32_t hv)
{
    assoc_entry_t **before = hashitem_before(key, nkey, hv);
    if (*before) {
        assoc_entry_t *entry = *before;
        *before = entry->h_next;
        entry->h_next = 0;
#ifdef INTERSPEC_FAULT_TESTS
        if (g_fault_mode == 2 && !g_fault_used) {
            g_fault_used = 1;
            g_kept = entry;      /* removed from the chain, but remembered */
            return;
        }
#endif
        free(entry);
    }
}

/* The walk functions: assoc_get_iterator, assoc_iterate, assoc_iterate_final. */
struct assoc_iterator {
    uint64_t bucket;
    assoc_entry_t *it;
    assoc_entry_t *next;
    int bucket_locked;
    uintptr_t current;           /* *it of the last assoc_iterate call */
};

uintptr_t interspec_assoc_get_iterator(void)
{
    return (uintptr_t)calloc(1, sizeof(struct assoc_iterator));
}

int interspec_assoc_iterate(uintptr_t iterp)
{
    struct assoc_iterator *iter = (struct assoc_iterator *)iterp;
    iter->current = 0;
    if (iter->bucket_locked) {
        if (iter->next != NULL) {
            iter->it = iter->next;
            iter->next = iter->it->h_next;
            iter->current = iter->it->item;
        } else {
            iter->bucket++;
            iter->bucket_locked = 0;
        }
        return 1;
    }
    if (iter->bucket != hashsize(hashpower)) {
        iter->bucket_locked = 1;
        iter->it = primary_hashtable[iter->bucket];
        if (iter->it != NULL) {
            iter->next = iter->it->h_next;
            iter->current = iter->it->item;
        } else {
            iter->bucket_locked = 0;
            iter->bucket++;
        }
    } else {
        return 0;
    }
    return 1;
}

uintptr_t interspec_assoc_iterate_item(uintptr_t iterp)
{
    return ((struct assoc_iterator *)iterp)->current;
}

void interspec_assoc_iterate_final(uintptr_t iterp)
{
    free((void *)iterp);
}

/* Staging memory that T fills: 0 = key, 1 = item image. Zeroed when allocated. */
static unsigned char *g_stage[2];
static uint32_t g_stage_capacity[2];

unsigned char *interspec_assoc_stage(uint32_t which, uint32_t bytes)
{
    if (which > 1) return NULL;
    if (bytes > g_stage_capacity[which]) {
        free(g_stage[which]);
        g_stage[which] = calloc(1, bytes);
        g_stage_capacity[which] = g_stage[which] ? bytes : 0;
    }
    return g_stage[which];
}
