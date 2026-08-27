#include <interspec/runtime.h>

#include <cstdlib>
#include <iostream>

int main() {
  constexpr uintptr_t kBase = 0x60000000;
  constexpr interspec::TypeId kItemId = 1;
  constexpr uint64_t kItem = interspec::type_hash("Item");

  interspec::Runtime runtime(kBase, 4096);
  if (!runtime.register_type(kItemId, kItem)) return EXIT_FAILURE;

  const uintptr_t item = runtime.allocate(32, kItemId);
  if (!item) return EXIT_FAILURE;
  if (runtime.check(item + 8, 8, kItem) != interspec::CheckResult::ok)
    return EXIT_FAILURE;

  std::cout << "installed InterSpec runtime consumer: ok\n";
  return EXIT_SUCCESS;
}
