#include "typed_arena.h"

#include <cstdlib>
#include <iostream>

using interspec::CheckResult;
using interspec::TypedArena;
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

  TypedArena arena(kArenaBase, 4096);
  const uintptr_t item = arena.allocate(80, kItem);
  const uintptr_t other = arena.allocate(80, kOther);

  EXPECT(arena.check(item, 80, kItem), CheckResult::ok);
  EXPECT(arena.check(other, 80, kItem), CheckResult::wrong_type);
  EXPECT(arena.check(item, 81, kItem), CheckResult::out_of_bounds);
  EXPECT(arena.check(item + 16, 32, kItem), CheckResult::ok);
  EXPECT(arena.check(item + 16, 65, kItem), CheckResult::out_of_bounds);
  EXPECT(arena.check(0x50000000, 8, kItem), CheckResult::untracked);

  EXPECT(arena.release(item), true);
  EXPECT(arena.check(item, 8, kItem), CheckResult::untracked);

  std::cout << "typed allocator PoC: all checks passed\n";
  return EXIT_SUCCESS;
}
