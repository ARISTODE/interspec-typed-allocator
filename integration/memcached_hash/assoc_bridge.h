/* Shared by U (assoc_u.c) and T: what crosses the memcached/hash boundary
 * when memcached's hash table runs in U (tracker item I9, JH decision of
 * 2026-11-14). This cut is not in the interspec-artifact, which isolates the
 * hash function only.
 *
 * memcached's assoc.c reads three things of an item: nkey, the key bytes, and
 * the chain field h_next, which it also writes. Inside a sandbox it cannot
 * read T's item, so the wrapper hands it an image of the item, and U keeps the
 * image as its table entry. T's item itself is named by a handle. */
#ifndef INTERSPEC_ASSOC_BRIDGE_H
#define INTERSPEC_ASSOC_BRIDGE_H

#include <stdint.h>

/* Fixed layout of the header fields of memcached's `item` (struct _stritem at
 * the pinned revision), with pointers as 32-bit values. The key (nkey bytes)
 * and then the value (nbytes bytes) follow the header. */
typedef struct assoc_item_image_s {
    uint32_t next;       /* LRU links: T pointers */
    uint32_t prev;
    uint32_t h_next;     /* hash chain: the only field assoc.c writes */
    uint32_t time;
    uint32_t exptime;
    int32_t nbytes;
    uint16_t refcount;
    uint16_t it_flags;
    uint8_t slabs_clsid;
    uint8_t nkey;        /* read by assoc.c */
    uint8_t reserved[2];
} assoc_item_image_t;

#define ASSOC_IMAGE_KEY(image) ((char *)(image) + sizeof(assoc_item_image_t))
#define ASSOC_IMAGE_VALUE(image) (ASSOC_IMAGE_KEY(image) + (image)->nkey)

#endif
