#include "interspec/runtime.h"

#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>

int main() {
  constexpr uint64_t kChar = interspec::type_hash("char");
  constexpr uint64_t kOther = interspec::type_hash("other");

  interspec::Runtime runtime(0x1000, 0x1000);
  assert(runtime.register_type(1, kChar));
  assert(runtime.register_type(2, kOther));

  assert(runtime.register_allocation_site_id(7, 1));
  assert(!runtime.register_allocation_site_id(7, 2));
  assert(runtime.allocation_site_count() == 1);

  const uintptr_t ptr = runtime.allocate_from_site(24, 7);
  assert(ptr == 0x1000);
  assert(runtime.check(ptr, 24, kChar) == interspec::CheckResult::ok);
  assert(runtime.check(ptr, 1, kOther) == interspec::CheckResult::wrong_type);
  assert(runtime.check(ptr + 23, 2, kChar) == interspec::CheckResult::out_of_bounds);

  interspec::SiteId site = 0;
  assert(runtime.allocation_site(ptr, site));
  assert(site == 7);

  assert(runtime.register_allocation_site(8, 0x200, 0x210, 2));
  assert(runtime.allocation_site_count() == 2);
  const uintptr_t from_pc = runtime.allocate_from_pc(8, 0x205);
  assert(from_pc != 0);
  assert(runtime.check(from_pc, 8, kOther) == interspec::CheckResult::ok);
  assert(runtime.allocation_site(from_pc, site));
  assert(site == 8);

  std::cout << "InterSpec P9b trusted site-id runtime binding: all checks passed\n";
  return 0;
}
