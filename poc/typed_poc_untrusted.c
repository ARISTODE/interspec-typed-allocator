#include "interspec_u_policy.h"

#include <stdint.h>
#include <stdlib.h>
#include <sys/mman.h>

typedef uint32_t (*alloc_fn)(uint32_t, uint32_t);
typedef int (*free_fn)(uint32_t);

static alloc_fn typed_alloc;
static free_fn typed_free;

struct Item {
  uint32_t id;
  uint32_t value;
};

struct Other {
  uint64_t value;
};

void typed_poc_init(alloc_fn alloc, free_fn free_cb) {
  typed_alloc = alloc;
  typed_free = free_cb;
}

unsigned char* typed_poc_make_item(void) {
  struct Item* item = (struct Item*)malloc(sizeof(struct Item));
  if (!item) return 0;
  item->id = 1;
  item->value = 42;
  return (unsigned char*)item;
}

unsigned char* typed_poc_make_other(void) {
  struct Other* other = (struct Other*)malloc(sizeof(struct Other));
  if (!other) return 0;
  other->value = 42;
  return (unsigned char*)other;
}

/* Adversarial direct request: U can select a registered ID, not redefine it. */
unsigned char* typed_poc_make_item_from_other_site(void) {
  uint32_t ptr = typed_alloc(sizeof(struct Item), INTERSPEC_TYPE_ID_OTHER);
  struct Item* item = (struct Item*)(uintptr_t)ptr;
  if (!item) return 0;
  item->id = 1;
  item->value = 42;
  return (unsigned char*)item;
}

unsigned char* typed_poc_try_unknown_type(void) {
  uint32_t ptr = typed_alloc(sizeof(struct Item), UINT32_C(999));
  return (unsigned char*)(uintptr_t)ptr;
}

unsigned char* typed_poc_make_untracked(void) {
  return (unsigned char*)malloc(sizeof(struct Item));
}

int typed_poc_release(unsigned char* ptr) {
  return typed_free((uint32_t)(uintptr_t)ptr);
}

void typed_poc_release_untracked(unsigned char* ptr) {
  free(ptr);
}

int typed_poc_try_munmap(uint32_t start, uint32_t size) {
  return munmap((void*)(uintptr_t)start, size);
}

int typed_poc_try_mprotect(uint32_t start, uint32_t size) {
  return mprotect((void*)(uintptr_t)start, size, PROT_READ);
}

int typed_poc_try_remap(uint32_t start, uint32_t size) {
  void* result = mmap((void*)(uintptr_t)start,
                      size,
                      PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED,
                      -1,
                      0);
  return result == MAP_FAILED ? -1 : 0;
}
