#include "interspec/pointer_census.h"
#include <cassert>
#include <cstdlib>
#include <cstring>

namespace { int kStaticValue = 13; }

int main() {
  int stack_value = 23;
  assert(std::strcmp(interspec::census::host_storage(nullptr), "null") == 0);
#if defined(__linux__)
  assert(std::strcmp(interspec::census::host_storage(&stack_value), "t_stack") == 0);
  assert(std::strcmp(interspec::census::host_storage(&kStaticValue), "t_image_static") == 0);
#endif
  int* heap = static_cast<int*>(std::malloc(sizeof(int)));
  assert(heap);
  assert(std::strcmp(interspec::census::host_storage(heap), "unknown") == 0);
  std::free(heap);
  setenv("INTERSPEC_POINTER_CENSUS", "1", 1);
  interspec::census::trusted_input("test", "stack", &stack_value);
  interspec::census::trusted_adapter_reference("test", "global", &kStaticValue);
  interspec::census::sandbox_result("test", "checked", 0x1000u, true);
  return 0;
}

