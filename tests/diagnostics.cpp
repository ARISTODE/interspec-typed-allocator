#include <interspec/runtime.h>
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <limits>

int main() {
  using namespace interspec;
  Runtime runtime(0x1000, 4096);
  constexpr auto type = type_hash("char");
  assert(runtime.register_type(1, type));
  assert(runtime.register_allocation_site_id(7, 1));
  const auto ptr = runtime.allocate_from_site(16, 7);
  assert(ptr == 0x1000);
  size_t remaining = 0;
  assert(runtime.remaining_bytes(ptr + 12, type, remaining) == CheckResult::ok);
  assert(remaining == 4);
  assert(runtime.check(ptr + 12, 5, type) == CheckResult::out_of_bounds);
  assert(runtime.check(ptr, 1, type_hash("Other")) == CheckResult::wrong_type);
  assert(runtime.check(ptr, std::numeric_limits<size_t>::max(), type) == CheckResult::out_of_bounds);
  runtime.dump_allocations();
  const auto replacement = runtime.reallocate(ptr, 24);
  assert(replacement && replacement != ptr);
  assert(runtime.check(ptr, 1, type) == CheckResult::untracked);
  assert(runtime.release(replacement));
  assert(runtime.check(replacement, 1, type) == CheckResult::untracked);
  assert(runtime.allocation_count() == 0);
}
