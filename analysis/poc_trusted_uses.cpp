#include <cstdint>

struct Item {
  uint32_t id;
  uint32_t value;
};

struct Other {
  uint64_t value;
};

uint32_t trusted_use_item(const Item* item) {
  return item->value;
}

uint64_t trusted_use_other(const Other* other) {
  return other->value;
}
