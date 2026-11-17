// Handles for objects of T that U names without their address: the dense
// handle table, the rule that no handle is issued twice, and the check that
// resolves a handle to its object.
// Built twice by CMake, with and without INTERSPEC_SINGLE_THREADED_REGISTRY.
#include <interspec/runtime.h>

#include <cstdint>
#include <iostream>
#include <random>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using interspec::CheckResult;
using interspec::HandleTable;
using interspec::MemoryDomain;
using interspec::Runtime;
using interspec::type_hash;

#define EXPECT_EQ(actual, expected)                                            \
  do {                                                                         \
    const auto observed = (actual);                                           \
    const auto wanted = (expected);                                           \
    if (observed != wanted) {                                                 \
      std::cerr << "runtime_handle_table failed at line " << __LINE__ << '\n';\
      return 1;                                                                \
    }                                                                         \
  } while (0)

struct Item {
  std::uint64_t a, b;
};
struct Other {
  std::uint64_t a;
};

int main() {
  // 1. The table against a model, with random registrations and releases.
  //    Every handle ever issued is remembered: none may come back, and a
  //    released one must not resolve.
  {
    HandleTable table;
    std::unordered_map<std::uint32_t, std::uintptr_t> live;
    std::unordered_set<std::uint32_t> issued;
    std::vector<std::uint32_t> released;
    std::vector<std::uint32_t> order;
    std::mt19937_64 rng(7);
    for (int step = 0; step < 300000; step++) {
      const unsigned kind = static_cast<unsigned>(rng() % 10);
      if (kind < 5 || live.empty()) {
        const std::uintptr_t base = 0x1000 + 16 * static_cast<std::uintptr_t>(step);
        const std::uint32_t handle = table.insert(base, 16, 99, MemoryDomain::trusted);
        EXPECT_EQ(handle != 0, true);
        EXPECT_EQ(issued.insert(handle).second, true);  // never issued before
        live.emplace(handle, base);
        order.push_back(handle);
      } else if (kind < 8) {
        const std::uint32_t handle = order[rng() % order.size()];
        const bool was_live = live.erase(handle) == 1;
        EXPECT_EQ(table.erase(handle), was_live);
        if (was_live) released.push_back(handle);
      } else {
        const std::uint32_t handle = order[rng() % order.size()];
        const HandleTable::Record* record = table.find(handle);
        const auto expected = live.find(handle);
        EXPECT_EQ(record != nullptr, expected != live.end());
        if (record) EXPECT_EQ(record->base, expected->second);
      }
      EXPECT_EQ(table.size(), live.size());
    }
    for (const std::uint32_t handle : released) EXPECT_EQ(table.find(handle) == nullptr, true);
    for (const auto& entry : live) EXPECT_EQ(table.find(entry.first)->base, entry.second);
    EXPECT_EQ(table.find(0) == nullptr, true);
    EXPECT_EQ(table.find(~std::uint32_t{0}) == nullptr, true);
    EXPECT_EQ(table.erase(0), false);
  }

  // 2. A slot is retired when its generations are used up: the handles of one
  //    slot are all different, and after the last one the slot is not reused.
  {
    HandleTable table;
    std::unordered_set<std::uint32_t> seen;
    std::uint32_t last = 0;
    for (std::uint32_t round = 0; round < HandleTable::kLastGeneration; round++) {
      last = table.insert(0x2000, 8, 1, MemoryDomain::trusted);
      EXPECT_EQ(last & HandleTable::kSlotMask, 0u);  // always slot 0
      EXPECT_EQ(seen.insert(last).second, true);
      EXPECT_EQ(table.erase(last), true);
    }
    const std::uint32_t next = table.insert(0x2000, 8, 1, MemoryDomain::trusted);
    EXPECT_EQ(next & HandleTable::kSlotMask, 1u);  // slot 0 is retired
    for (const std::uint32_t handle : seen) EXPECT_EQ(table.find(handle) == nullptr, true);
    // A handle that names slot 0 with a generation never issued for it.
    EXPECT_EQ(table.find(last + (1u << HandleTable::kSlotBits)) == nullptr, true);
  }

  // 3. The registry: what register_handle refuses and what resolve_handle
  //    answers.
  {
    alignas(16) static unsigned char arena[4096];
    Runtime runtime(reinterpret_cast<std::uintptr_t>(arena), sizeof(arena));
    const std::uint64_t item = type_hash("item"), other = type_hash("other");
    EXPECT_EQ(runtime.register_type(1, item), true);
    EXPECT_EQ(runtime.register_type_layout(1, sizeof(Item), alignof(Item)), true);
    EXPECT_EQ(runtime.register_type(2, other), true);
    EXPECT_EQ(runtime.register_type_layout(2, sizeof(Other), alignof(Other)), true);
    EXPECT_EQ(runtime.register_type(3, type_hash("no_layout")), true);

    static Item items[4];
    static Other others[1];
    const auto address = [](const void* p) { return reinterpret_cast<std::uintptr_t>(p); };
    EXPECT_EQ(runtime.register_handle(0, 1, 1, MemoryDomain::trusted), 0u);
    EXPECT_EQ(runtime.register_handle(address(items), 0, 1, MemoryDomain::trusted), 0u);
    EXPECT_EQ(runtime.register_handle(address(items), 1, 9, MemoryDomain::trusted), 0u);
    EXPECT_EQ(runtime.register_handle(address(items), 1, 3, MemoryDomain::trusted), 0u);
    EXPECT_EQ(runtime.register_handle(address(items) + 1, 1, 1, MemoryDomain::trusted), 0u);
    EXPECT_EQ(runtime.register_handle(address(arena), 1, 1, MemoryDomain::trusted), 0u);
    EXPECT_EQ(runtime.handle_count(), 0u);

    const std::uint32_t one = runtime.register_handle(address(&items[0]), 1, 1, MemoryDomain::trusted);
    const std::uint32_t two = runtime.register_handle(address(&items[1]), 2, 1, MemoryDomain::trusted);
    const std::uint32_t odd = runtime.register_handle(address(others), 1, 2, MemoryDomain::trusted);
    const std::uint32_t u = runtime.register_handle(address(&items[3]), 1, 1, MemoryDomain::untrusted);
    EXPECT_EQ(one != 0 && two != 0 && odd != 0 && u != 0, true);
    EXPECT_EQ(runtime.handle_count(), 4u);
    // The layout of a type with a registered object cannot change.
    EXPECT_EQ(runtime.register_type_layout(1, 2 * sizeof(Item), alignof(Item)), false);

    std::uintptr_t base = 1;
    EXPECT_EQ(runtime.resolve_handle(one, sizeof(Item), item, MemoryDomain::trusted, base),
              CheckResult::ok);
    EXPECT_EQ(base, address(&items[0]));
    base = 1;
    EXPECT_EQ(runtime.resolve_handle(two, 2 * sizeof(Item), item, MemoryDomain::trusted, base),
              CheckResult::ok);
    EXPECT_EQ(base, address(&items[1]));
    base = 1;
    EXPECT_EQ(runtime.resolve_handle(one, sizeof(Item) + 1, item, MemoryDomain::trusted, base),
              CheckResult::out_of_bounds);
    EXPECT_EQ(runtime.resolve_handle(odd, sizeof(Other), item, MemoryDomain::trusted, base),
              CheckResult::wrong_type);
    EXPECT_EQ(runtime.resolve_handle(u, sizeof(Item), item, MemoryDomain::trusted, base),
              CheckResult::wrong_domain);
    EXPECT_EQ(runtime.resolve_handle(0, sizeof(Item), item, MemoryDomain::trusted, base),
              CheckResult::untracked);
    EXPECT_EQ(runtime.resolve_handle(~std::uint32_t{0}, sizeof(Item), item,
                                     MemoryDomain::trusted, base),
              CheckResult::untracked);
    EXPECT_EQ(runtime.resolve_handle(one + 1, sizeof(Item), item, MemoryDomain::trusted, base),
              CheckResult::ok);  // `two`: handles of neighbouring slots differ by one
    EXPECT_EQ(base, address(&items[1]));
    base = 1;
    EXPECT_EQ(runtime.resolve_handle(0x5ec2e7f0u, sizeof(Item), item, MemoryDomain::trusted, base),
              CheckResult::untracked);
    EXPECT_EQ(base, std::uintptr_t{1});  // written only on ok

    // After release the handle is refused, also when the same object is
    // registered again: the new handle is a different value.
    EXPECT_EQ(runtime.unregister_handle(one), true);
    EXPECT_EQ(runtime.unregister_handle(one), false);
    EXPECT_EQ(runtime.resolve_handle(one, sizeof(Item), item, MemoryDomain::trusted, base),
              CheckResult::untracked);
    const std::uint32_t again =
        runtime.register_handle(address(&items[0]), 1, 1, MemoryDomain::trusted);
    EXPECT_EQ(again != 0 && again != one, true);
    EXPECT_EQ(runtime.resolve_handle(one, sizeof(Item), item, MemoryDomain::trusted, base),
              CheckResult::untracked);
    EXPECT_EQ(runtime.resolve_handle(again, sizeof(Item), item, MemoryDomain::trusted, base),
              CheckResult::ok);
    std::uintptr_t unchecked = 0;
    EXPECT_EQ(runtime.handle_base(again, unchecked), true);
    EXPECT_EQ(unchecked, address(&items[0]));
    EXPECT_EQ(runtime.handle_base(one, unchecked), false);

    // Handles are apart from the objects registered by address.
    EXPECT_EQ(runtime.unregister_external(again), false);
  }
  std::cout << "runtime_handle_table ok\n";
  return 0;
}
