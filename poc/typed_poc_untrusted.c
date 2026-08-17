#include <stdint.h>
#include <stdlib.h>

typedef unsigned char* (*alloc_fn)(uint32_t, uint64_t);
typedef int (*free_fn)(unsigned char*);

static alloc_fn typed_alloc;
static free_fn typed_free;

enum {
  ITEM_HASH = 158651791ULL,
  OTHER_HASH = 22127667330ULL,
};

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
  struct Item* item = (struct Item*)typed_alloc(sizeof(struct Item), ITEM_HASH);
  if (!item) return 0;
  item->id = 1;
  item->value = 42;
  return (unsigned char*)item;
}

unsigned char* typed_poc_make_other(void) {
  struct Other* other = (struct Other*)typed_alloc(sizeof(struct Other), OTHER_HASH);
  if (!other) return 0;
  other->value = 42;
  return (unsigned char*)other;
}

unsigned char* typed_poc_make_untracked(void) {
  return (unsigned char*)malloc(sizeof(struct Item));
}

int typed_poc_release(unsigned char* ptr) {
  return typed_free(ptr);
}

void typed_poc_release_untracked(unsigned char* ptr) {
  free(ptr);
}
