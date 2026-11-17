// The registry's records of U's allocations (tracker item R1).
//
// The records are blocks of the arena in a dense array with an index by
// address (see allocate_with_hash_unlocked in runtime.h). This test compares
// the registry with a model that keeps the live objects in a std::map, over a
// random sequence of allocations, releases and reallocations at several sites
// and with typed arrays of two alignments. After every step it checks, for
// pointers to the beginning, the interior, the last byte and one past the end
// of objects, for released objects and for addresses in padding, that the
// registry answers as the model does. Every comparison is counted; the test
// fails if any differs.
#include "interspec/runtime.h"

#include <cstdint>
#include <cstdio>
#include <map>
#include <random>
#include <vector>

namespace {

unsigned long comparisons = 0, failures = 0;

#define EXPECT(condition)                                                    \
  do {                                                                       \
    ++comparisons;                                                           \
    if (!(condition)) {                                                      \
      if (++failures <= 20)                                                  \
        std::printf("FAIL line %d: %s\n", __LINE__, #condition);             \
    }                                                                        \
  } while (0)

using interspec::CheckResult;
using interspec::Runtime;

struct Object {
  size_t size;
  uint64_t type;
  interspec::SiteId site;
};

constexpr uint64_t kTypes[] = {interspec::type_hash("a"), interspec::type_hash("b"),
                               interspec::type_hash("wide")};
constexpr interspec::SiteId kSites[] = {21, 22, 23};  // 21, 22: type a; 23: type b
constexpr uintptr_t kBase = 0x40000;
constexpr size_t kArena = 4 << 20;

uint64_t type_of_site(interspec::SiteId site) { return site == 23 ? kTypes[1] : kTypes[0]; }

// What the registry must answer for `ptr`, from the model.
void compare(const Runtime& runtime, const std::map<uintptr_t, Object>& model, uintptr_t ptr) {
  const Object* object = nullptr;
  uintptr_t base = 0;
  auto next = model.upper_bound(ptr);
  if (next != model.begin()) {
    --next;
    if (ptr - next->first < next->second.size) {
      object = &next->second;
      base = next->first;
    }
  }
  for (const uint64_t type : kTypes) {
    const CheckResult got = runtime.check(ptr, 1, type);
    if (!object) {
      EXPECT(got == CheckResult::untracked);
    } else if (object->type != type) {
      EXPECT(got == CheckResult::wrong_type);
    } else {
      EXPECT(got == CheckResult::ok);
      const size_t remaining = object->size - (ptr - base);
      EXPECT(runtime.check(ptr, remaining, type) == CheckResult::ok);
      EXPECT(runtime.check(ptr, remaining + 1, type) == CheckResult::out_of_bounds);
      size_t bytes = 0;
      EXPECT(runtime.remaining_bytes(ptr, type, bytes) == CheckResult::ok && bytes == remaining);
    }
  }
  size_t size = 0;
  interspec::SiteId site = 0;
  const bool is_base = object && base == ptr;
  EXPECT(runtime.allocation_size(ptr, size) == is_base);
  EXPECT(runtime.allocation_site(ptr, site) == is_base);
  if (is_base) EXPECT(size == object->size && site == object->site);
}

void random_sequence(unsigned seed, int steps) {
  Runtime runtime(kBase, kArena);
  EXPECT(runtime.register_type(1, kTypes[0]));
  EXPECT(runtime.register_type(2, kTypes[1]));
  EXPECT(runtime.register_type(3, kTypes[2]));
  EXPECT(runtime.register_type_layout(3, 96, 32));
  EXPECT(runtime.register_allocation_site_id(21, 1));
  EXPECT(runtime.register_allocation_site_id(22, 1));
  EXPECT(runtime.register_allocation_site_id(23, 2));

  std::mt19937 rng(seed);
  std::map<uintptr_t, Object> model;
  // Every address that was ever the base of an object, with the site that
  // owns it: an address must never move to another site.
  std::map<uintptr_t, interspec::SiteId> owner;
  std::vector<uintptr_t> live, released;
  size_t most = 0;
  auto pick = [&](std::vector<uintptr_t>& from) {
    const size_t i = rng() % from.size();
    const uintptr_t value = from[i];
    from[i] = from.back();
    from.pop_back();
    return value;
  };
  auto record = [&](uintptr_t ptr, size_t size, uint64_t type, interspec::SiteId site) {
    EXPECT(ptr >= kBase && ptr + size <= kBase + kArena);
    // No overlap with a live object.
    auto next = model.lower_bound(ptr);
    EXPECT(next == model.end() || ptr + size <= next->first);
    if (next != model.begin()) {
      auto prev = std::prev(next);
      EXPECT(prev->first + prev->second.size <= ptr);
    }
    const auto known = owner.emplace(ptr, site);
    EXPECT(known.second || known.first->second == site);
    model[ptr] = Object{size, type, site};
    live.push_back(ptr);
  };

  for (int step = 0; step < steps; ++step) {
    // The population grows in the first half and shrinks in the second.
    const unsigned grow = step < steps / 2 ? 60 : 30;
    const unsigned action = rng() % 100;
    if (action < grow || live.empty()) {
      if (rng() % 8 == 0) {  // typed array: 96-byte elements, 32-byte alignment
        const size_t count = 1 + rng() % 5;
        const uintptr_t ptr = runtime.allocate_typed_array(count, 3);
        if (ptr) {
          EXPECT(ptr % 32 == 0);
          record(ptr, 96 * count, kTypes[2], 0);
          EXPECT(runtime.check_typed_element(ptr + 96 * (count - 1), 96, kTypes[2]) == CheckResult::ok);
          EXPECT(runtime.check_typed_element(ptr + 8, 8, kTypes[2]) == CheckResult::out_of_bounds);
        }
      } else {
        const interspec::SiteId site = kSites[rng() % 3];
        // Mostly small objects, some that span many lines of the index.
        const size_t size = rng() % 16 == 0 ? 1 + rng() % 5000 : 1 + rng() % 120;
        const uintptr_t ptr = runtime.allocate_from_site(size, site);
        if (ptr) record(ptr, size, type_of_site(site), site);
      }
    } else if (action < 85) {
      const uintptr_t ptr = pick(live);
      EXPECT(runtime.release(ptr));
      EXPECT(!runtime.release(ptr));
      model.erase(ptr);
      released.push_back(ptr);
    } else {
      const uintptr_t ptr = pick(live);
      const Object old = model[ptr];
      if (old.site == 0) {  // typed arrays keep their stride
        live.push_back(ptr);
        continue;
      }
      const size_t size = 1 + rng() % 300;
      const uintptr_t moved = runtime.reallocate(ptr, size);
      if (!moved) {
        live.push_back(ptr);
        continue;
      }
      EXPECT(moved != ptr);
      model.erase(ptr);
      released.push_back(ptr);
      record(moved, size, old.type, old.site);
    }
    EXPECT(runtime.allocation_count() == model.size());
    if (model.size() > most) most = model.size();

    // Probes: objects (begin, interior, last byte, one past the end), released
    // addresses, and random addresses of the arena and around it.
    for (int probe = 0; probe < 6 && !live.empty(); ++probe) {
      const uintptr_t base = live[rng() % live.size()];
      const size_t size = model[base].size;
      compare(runtime, model, base);
      compare(runtime, model, base + rng() % size);
      compare(runtime, model, base + size - 1);
      compare(runtime, model, base + size);
      if (base > kBase) compare(runtime, model, base - 1);
    }
    if (!released.empty()) compare(runtime, model, released[rng() % released.size()]);
    compare(runtime, model, kBase + rng() % (kArena + 256));
    compare(runtime, model, kBase - 1 - rng() % 64);
  }
  // At the end, every live object and every byte of a few of them.
  for (const auto& entry : model) compare(runtime, model, entry.first);
  for (int i = 0; i < 20 && !live.empty(); ++i) {
    const uintptr_t base = live[rng() % live.size()];
    for (size_t offset = 0; offset <= model[base].size; ++offset)
      compare(runtime, model, base + offset);
  }
  std::printf("seed %u: %d steps, at most %zu live objects, %zu at the end, %zu addresses ever used\n",
              seed, steps, most, model.size(), owner.size());
}

// Objects of the smallest size fill a line of the index completely: eight
// blocks begin in one line, and each must be found.
void smallest_objects() {
  Runtime runtime(kBase, 4096);
  EXPECT(runtime.register_type(1, kTypes[0]));
  EXPECT(runtime.register_allocation_site_id(21, 1));
  std::vector<uintptr_t> objects;
  for (int i = 0; i < 512; ++i) {
    const uintptr_t ptr = runtime.allocate_from_site(1 + i % 8, 21);
    EXPECT(ptr == kBase + 8 * static_cast<uintptr_t>(i));
    objects.push_back(ptr);
  }
  EXPECT(runtime.allocate_from_site(1, 21) == 0);  // the arena is full
  for (int i = 0; i < 512; ++i) {
    const size_t size = 1 + i % 8;
    EXPECT(runtime.check(objects[i], size, kTypes[0]) == CheckResult::ok);
    EXPECT(runtime.check(objects[i] + size - 1, 1, kTypes[0]) == CheckResult::ok);
    if (size < 8) EXPECT(runtime.check(objects[i] + size, 1, kTypes[0]) == CheckResult::untracked);
  }
  for (int i = 0; i < 512; i += 2) EXPECT(runtime.release(objects[i]));
  for (int i = 0; i < 512; ++i)
    EXPECT(runtime.check(objects[i], 1, kTypes[0]) ==
           (i % 2 ? CheckResult::ok : CheckResult::untracked));
  EXPECT(runtime.allocation_count() == 256);
}

}  // namespace

int main() {
  smallest_objects();
  for (unsigned seed = 1; seed <= 8; ++seed) random_sequence(seed, 20000);  // up to several thousand live objects
  std::printf("%lu comparisons, %lu failures\n", comparisons, failures);
  return failures ? 1 : 0;
}
