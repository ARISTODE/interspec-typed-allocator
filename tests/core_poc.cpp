#include <interspec/runtime.h>

#include <cstdlib>
#include <iostream>

using interspec::CheckResult;
using interspec::Runtime;
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

  Runtime runtime(kArenaBase, 4096);
  const uintptr_t item = runtime.allocate(80, kItem);
  const uintptr_t other = runtime.allocate(80, kOther);

  EXPECT(runtime.check(item, 80, kItem), CheckResult::ok);
  EXPECT(runtime.check(other, 80, kItem), CheckResult::wrong_type);
  EXPECT(runtime.check(item, 81, kItem), CheckResult::out_of_bounds);
  EXPECT(runtime.check(item + 16, 32, kItem), CheckResult::ok);
  EXPECT(runtime.check(item + 16, 65, kItem), CheckResult::out_of_bounds);
  EXPECT(runtime.check(0x50000000, 8, kItem), CheckResult::untracked);

  EXPECT(runtime.release(item), true);
  EXPECT(runtime.check(item, 8, kItem), CheckResult::untracked);

  std::cout << "InterSpec runtime: all checks passed\n";
  return EXIT_SUCCESS;
}
