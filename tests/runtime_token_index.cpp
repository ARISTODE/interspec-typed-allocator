// Tokens of externally registered objects: the flat token index, the check
// that resolves a token to its object, and the registry without its lock.
// Built twice by CMake, with and without INTERSPEC_SINGLE_THREADED_REGISTRY.
#include <interspec/runtime.h>

#include <cstdint>
#include <iostream>
#include <map>
#include <random>
#include <vector>

using interspec::CheckResult;
using interspec::MemoryDomain;
using interspec::ObjectStorage;
using interspec::Runtime;
using interspec::type_hash;

#define EXPECT_EQ(actual, expected)                                           \
  do {                                                                        \
    const auto observed = (actual);                                          \
    const auto wanted = (expected);                                          \
    if (observed != wanted) {                                                \
      std::cerr << "runtime_token_index failed at line " << __LINE__ << '\n';\
      return 1;                                                               \
    }                                                                        \
  } while (0)

struct Item {
  std::uint64_t a, b;
};
struct Other {
  std::uint64_t a;
};

int main() {
#ifdef INTERSPEC_SINGLE_THREADED_REGISTRY
  EXPECT_EQ(interspec::kRegistryLocked, false);
#else
  EXPECT_EQ(interspec::kRegistryLocked, true);
#endif
  constexpr uint32_t kItemId = 1, kOtherId = 2;
  constexpr uint64_t kItem = type_hash("Item"), kOther = type_hash("Other");
  Runtime runtime(0, 0);
  EXPECT_EQ(runtime.register_type(kItemId, kItem), true);
  EXPECT_EQ(runtime.register_type_layout(kItemId, sizeof(Item), alignof(Item)), true);
  EXPECT_EQ(runtime.register_type(kOtherId, kOther), true);
  EXPECT_EQ(runtime.register_type_layout(kOtherId, sizeof(Other), alignof(Other)), true);

  // The index against a model: registrations and removals in random order,
  // enough of them to rebuild the table many times.
  std::vector<Item> items(4096);
  std::vector<uint64_t> token_of(items.size(), 0);
  std::map<uint64_t, size_t> live;  // token -> item
  std::vector<uint64_t> retired;
  std::mt19937_64 random(20261116);
  uint64_t last_token = 0;
  uintptr_t base = 0;
  for (int step = 0; step < 300000; ++step) {
    const size_t i = random() % items.size();
    const uintptr_t address = reinterpret_cast<uintptr_t>(&items[i]);
    if (token_of[i] == 0) {
      const uint64_t token = runtime.register_external_array(
          address, 1, kItemId, MemoryDomain::trusted, ObjectStorage::heap);
      EXPECT_EQ(token > last_token, true);  // never issued twice
      last_token = token;
      token_of[i] = token;
      live[token] = i;
      // The same storage cannot be registered a second time.
      EXPECT_EQ(runtime.register_external_array(address, 1, kItemId, MemoryDomain::trusted,
                                                ObjectStorage::heap), uint64_t{0});
    } else {
      EXPECT_EQ(runtime.unregister_external(token_of[i]), true);
      EXPECT_EQ(runtime.unregister_external(token_of[i]), false);
      live.erase(token_of[i]);
      if (retired.size() < 1024) retired.push_back(token_of[i]);
      token_of[i] = 0;
    }
    if (step % 97 == 0) {
      for (const auto& entry : live) {
        base = 0;
        EXPECT_EQ(runtime.resolve_external(entry.first, sizeof(Item), kItem,
                                           MemoryDomain::trusted, base), CheckResult::ok);
        EXPECT_EQ(base, reinterpret_cast<uintptr_t>(&items[entry.second]));
      }
      for (const uint64_t token : retired) {
        base = 7;
        EXPECT_EQ(runtime.resolve_external(token, sizeof(Item), kItem, MemoryDomain::trusted,
                                           base), CheckResult::untracked);
        EXPECT_EQ(base, uintptr_t{7});  // written only on ok
        EXPECT_EQ(runtime.external_base(token, base), false);
      }
    }
  }

  // What resolve_external refuses for a live token.
  Other other{1};
  const uint64_t other_token = runtime.register_external_array(
      reinterpret_cast<uintptr_t>(&other), 1, kOtherId, MemoryDomain::trusted,
      ObjectStorage::stack);
  EXPECT_EQ(other_token > last_token, true);
  base = 7;
  EXPECT_EQ(runtime.resolve_external(other_token, sizeof(Item), kItem, MemoryDomain::trusted,
                                     base), CheckResult::wrong_type);
  EXPECT_EQ(runtime.resolve_external(other_token, sizeof(Other), kOther,
                                     MemoryDomain::untrusted, base), CheckResult::wrong_domain);
  EXPECT_EQ(runtime.resolve_external(other_token, sizeof(Other) + 1, kOther,
                                     MemoryDomain::trusted, base), CheckResult::out_of_bounds);
  EXPECT_EQ(base, uintptr_t{7});
  EXPECT_EQ(runtime.resolve_external(other_token, sizeof(Other), kOther, MemoryDomain::trusted,
                                     base), CheckResult::ok);
  EXPECT_EQ(base, reinterpret_cast<uintptr_t>(&other));
  EXPECT_EQ(runtime.external_base(other_token, base), true);
  EXPECT_EQ(runtime.resolve_external(0, 1, kOther, MemoryDomain::trusted, base),
            CheckResult::untracked);
  EXPECT_EQ(runtime.resolve_external(~uint64_t{0}, 1, kOther, MemoryDomain::trusted, base),
            CheckResult::untracked);
  EXPECT_EQ(runtime.resolve_external(other_token + 1, 1, kOther, MemoryDomain::trusted, base),
            CheckResult::untracked);
  EXPECT_EQ(runtime.unregister_external(other_token), true);
  EXPECT_EQ(runtime.resolve_external(other_token, sizeof(Other), kOther, MemoryDomain::trusted,
                                     base), CheckResult::untracked);

  // The ordered index against a model. Byte arrays of random position and
  // length in one buffer: a registration must be refused exactly when it
  // overlaps a registered array, and a lookup by address must find exactly
  // the array that contains the address.
  {
    constexpr uint32_t kByteId = 3;
    constexpr uint64_t kByte = type_hash("Byte");
    Runtime ordered(0, 0);
    EXPECT_EQ(ordered.register_type(kByteId, kByte), true);
    EXPECT_EQ(ordered.register_type_layout(kByteId, 1, 1), true);
    std::vector<unsigned char> buffer(1u << 20);
    const uintptr_t origin = reinterpret_cast<uintptr_t>(buffer.data());
    struct Range { size_t length; uint64_t token; };
    std::map<size_t, Range> model;  // offset -> range
    std::vector<size_t> offsets;
    size_t accepted = 0, refused = 0;
    for (int step = 0; step < 400000; ++step) {
      const uint64_t r = random();
      if (r % 3 != 0 || offsets.empty()) {
        const size_t offset = (r >> 8) % buffer.size();
        const size_t length = 1 + (r >> 40) % ((r >> 60) % 4 == 0 ? 4096 : 48);
        if (offset + length > buffer.size()) continue;
        bool overlaps = false;
        auto next = model.lower_bound(offset);
        if (next != model.end() && offset + length > next->first) overlaps = true;
        if (next != model.begin()) {
          auto prev = std::prev(next);
          if (prev->first + prev->second.length > offset) overlaps = true;
        }
        const uint64_t token = ordered.register_external_array(
            origin + offset, length, kByteId, MemoryDomain::untrusted, ObjectStorage::heap);
        EXPECT_EQ(token != 0, !overlaps);
        if (token) {
          model[offset] = Range{length, token};
          offsets.push_back(offset);
          ++accepted;
        } else {
          ++refused;
        }
      } else {
        const size_t pick = (r >> 8) % offsets.size();
        const size_t offset = offsets[pick];
        offsets[pick] = offsets.back();
        offsets.pop_back();
        EXPECT_EQ(ordered.unregister_external(model[offset].token), true);
        model.erase(offset);
      }
      // A lookup by address: inside a range, or in a gap.
      const size_t probe = (random() >> 8) % buffer.size();
      auto after = model.upper_bound(probe);
      bool inside = false;
      if (after != model.begin()) {
        auto range = std::prev(after);
        inside = probe - range->first < range->second.length;
      }
      EXPECT_EQ(ordered.check_external_element_by_address(origin + probe, 1, kByte,
                                                          MemoryDomain::untrusted),
                inside ? CheckResult::ok : CheckResult::untracked);
    }
    EXPECT_EQ(accepted > 50000, true);
    EXPECT_EQ(refused > 50000, true);
    for (const auto& entry : model)
      EXPECT_EQ(ordered.unregister_external(entry.second.token), true);
    EXPECT_EQ(ordered.check_external_element_by_address(origin + 5, 1, kByte,
                                                        MemoryDomain::untrusted),
              CheckResult::untracked);
  }

  std::cout << "token index and token resolution: pass (registry "
            << (interspec::kRegistryLocked ? "locked" : "single-threaded") << ")\n";
  return 0;
}
