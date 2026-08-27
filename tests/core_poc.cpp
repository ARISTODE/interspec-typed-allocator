#include <interspec/runtime.h>

#include <cstdlib>
#include <iostream>

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
  constexpr uintptr_t kArenaBase = 0x40000000;
  constexpr uint64_t kItem = type_hash("Item");
  constexpr uint64_t kOther = type_hash("Other");
  constexpr TypeId kItemId = 1;
  constexpr TypeId kOtherId = 2;

  Runtime runtime(kArenaBase, 4096);
  EXPECT(runtime.register_type(kItemId, kItem), true);
  EXPECT(runtime.register_type(kOtherId, kOther), true);
  EXPECT(runtime.register_type(kItemId, kOther), false);
  EXPECT(runtime.allocate(80, 999), uintptr_t{0});

  const uintptr_t item = runtime.allocate(80, kItemId);
  const uintptr_t other = runtime.allocate(80, kOtherId);

  EXPECT(runtime.check(item, 80, kItem), CheckResult::ok);
  EXPECT(runtime.check(other, 80, kItem), CheckResult::wrong_type);
  EXPECT(runtime.check(item, 81, kItem), CheckResult::out_of_bounds);
  EXPECT(runtime.check(item + 16, 32, kItem), CheckResult::ok);
  EXPECT(runtime.check(item + 16, 65, kItem), CheckResult::out_of_bounds);
  EXPECT(runtime.check(0x50000000, 8, kItem), CheckResult::untracked);

  size_t remaining = 0;
  EXPECT(runtime.remaining_bytes(item + 16, kItem, remaining), CheckResult::ok);
  EXPECT(remaining, size_t{64});
  EXPECT(runtime.remaining_bytes(item, kOther, remaining), CheckResult::wrong_type);

  EXPECT(runtime.release(item), true);
  EXPECT(runtime.check(item, 8, kItem), CheckResult::untracked);

  std::cout << "InterSpec runtime: all checks passed\n";
  return EXIT_SUCCESS;
}
