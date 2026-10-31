#include "interspec/pointer_census.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#if defined(__linux__)
#include <sys/mman.h>
#endif

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
#if defined(__linux__)
  const char* heap_origin = interspec::census::host_storage(heap);
  assert(std::strcmp(heap_origin, "t_brk_heap_vma") == 0 ||
         std::strcmp(heap_origin, "t_anon_vma") == 0);
  void* mapping = mmap(nullptr, 4096, PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  assert(mapping != MAP_FAILED);
  assert(std::strcmp(interspec::census::host_storage(mapping),
                     "t_anon_vma") == 0);
  assert(munmap(mapping, 4096) == 0);
#else
  assert(std::strcmp(interspec::census::host_storage(heap), "unknown") == 0);
#endif
  std::free(heap);
  setenv("INTERSPEC_POINTER_CENSUS", "1", 1);
  interspec::census::trusted_input("test", "stack", &stack_value);
  interspec::census::trusted_adapter_reference("test", "global", &kStaticValue);
  interspec::census::sandbox_result("test", "checked", 0x1000u, true);
  return 0;
}

