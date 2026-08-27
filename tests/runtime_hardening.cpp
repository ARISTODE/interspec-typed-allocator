#include <interspec/runtime.h>

#include <atomic>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <thread>
#include <vector>

using interspec::CheckResult;
using interspec::Runtime;
using interspec::TypeId;
using interspec::type_hash;

#define EXPECT(actual, expected)                                               \
  do {                                                                         \
    if ((actual) != (expected)) {                                              \
      std::cerr << "failed at line " << __LINE__ << '\n';                     \
      return EXIT_FAILURE;                                                     \
    }                                                                          \
  } while (0)

int main() {
  constexpr uintptr_t kArenaBase = 0x50000000;
  constexpr uint64_t kItem = type_hash("Item");
  constexpr uint64_t kOther = type_hash("Other");
  constexpr TypeId kItemId = 1;
  constexpr TypeId kOtherId = 2;

  Runtime runtime(kArenaBase, 1u << 20);
  EXPECT(runtime.arena_valid(), true);
  EXPECT(runtime.capacity(), size_t{1u << 20});
  EXPECT(runtime.register_type(kItemId, kItem), true);
  EXPECT(runtime.register_type(kOtherId, kItem), false);
  EXPECT(runtime.register_type(kOtherId, kOther), true);

  const uintptr_t item = runtime.allocate(24, kItemId);
  EXPECT(item != 0, true);
  EXPECT(runtime.release(item + 1), false);
  EXPECT(runtime.check(item, 24, kItem), CheckResult::ok);

  const uintptr_t replacement = runtime.reallocate(item, 64);
  EXPECT(replacement != 0, true);
  EXPECT(replacement != item, true);
  EXPECT(runtime.check(item, 1, kItem), CheckResult::untracked);
  EXPECT(runtime.check(replacement, 64, kItem), CheckResult::ok);

  size_t replacement_size = 0;
  EXPECT(runtime.allocation_size(replacement, replacement_size), true);
  EXPECT(replacement_size, size_t{64});

  Runtime tight(kArenaBase, 64);
  EXPECT(tight.register_type(kItemId, kItem), true);
  const uintptr_t tight_item = tight.allocate(32, kItemId);
  EXPECT(tight_item != 0, true);
  EXPECT(tight.allocate(24, kItemId) != 0, true);
  EXPECT(tight.reallocate(tight_item, 16), uintptr_t{0});
  EXPECT(tight.check(tight_item, 32, kItem), CheckResult::ok);

  Runtime invalid(std::numeric_limits<uintptr_t>::max() - 3, 16);
  EXPECT(invalid.arena_valid(), false);
  EXPECT(invalid.register_type(kItemId, kItem), true);
  EXPECT(invalid.allocate(8, kItemId), uintptr_t{0});

  Runtime overflow(kArenaBase, 4096);
  EXPECT(overflow.register_type(kItemId, kItem), true);
  EXPECT(overflow.allocate(std::numeric_limits<size_t>::max(), kItemId),
         uintptr_t{0});

  Runtime stress(kArenaBase, 2u << 20);
  EXPECT(stress.register_type(kItemId, kItem), true);
  std::vector<uintptr_t> stress_ptrs;
  stress_ptrs.reserve(10000);
  for (size_t i = 0; i < 10000; ++i) {
    const uintptr_t ptr = stress.allocate(16, kItemId);
    if (!ptr) return EXIT_FAILURE;
    stress_ptrs.push_back(ptr);
  }
  EXPECT(stress.allocation_count(), size_t{10000});
  for (size_t i = 0; i < stress_ptrs.size(); i += 97) {
    EXPECT(stress.check(stress_ptrs[i] + 7, 9, kItem), CheckResult::ok);
    EXPECT(stress.check(stress_ptrs[i] + 7, 10, kItem),
           CheckResult::out_of_bounds);
  }

  Runtime concurrent(kArenaBase, 4u << 20);
  EXPECT(concurrent.register_type(kItemId, kItem), true);
  std::atomic<bool> failed{false};
  std::vector<std::thread> threads;
  constexpr int kThreads = 8;
  constexpr int kIterations = 512;

  for (int thread = 0; thread < kThreads; ++thread) {
    threads.emplace_back([&] {
      for (int i = 0; i < kIterations; ++i) {
        const uintptr_t ptr = concurrent.allocate(16, kItemId);
        if (!ptr || concurrent.check(ptr, 16, kItem) != CheckResult::ok) {
          failed.store(true);
          return;
        }

        size_t size = 0;
        if (!concurrent.allocation_size(ptr, size) || size != 16 ||
            !concurrent.release(ptr) ||
            concurrent.check(ptr, 1, kItem) != CheckResult::untracked) {
          failed.store(true);
          return;
        }
      }
    });
  }

  for (auto& thread : threads) thread.join();
  EXPECT(failed.load(), false);
  EXPECT(concurrent.allocation_count(), size_t{0});

  std::cout << "InterSpec runtime hardening: all checks passed\n";
  return EXIT_SUCCESS;
}
