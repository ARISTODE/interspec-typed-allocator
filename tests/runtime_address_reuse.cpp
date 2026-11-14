// Reuse of released addresses in the typed arena (JH decision of 2026-11-14).
//
// Rule under test: the address of a released object is handed out again only
// to a later allocation at the same site, and so of the same type. Every check
// is counted and reported; the test fails if any of them fails.
#include "interspec/runtime.h"

#include <cstdint>
#include <cstdio>
#include <vector>

namespace {

int failures = 0;

#define EXPECT(condition)                                                    \
  do {                                                                       \
    if (!(condition)) {                                                      \
      ++failures;                                                            \
      std::printf("FAIL line %d: %s\n", __LINE__, #condition);               \
    }                                                                        \
  } while (0)

using interspec::CheckResult;
using interspec::Runtime;

constexpr uint64_t kName = interspec::type_hash("name");
constexpr uint64_t kOther = interspec::type_hash("other");
constexpr interspec::SiteId kSiteA = 10, kSiteB = 11, kSiteOther = 12;

void set_up(Runtime& runtime) {
  EXPECT(runtime.register_type(1, kName));
  EXPECT(runtime.register_type(2, kOther));
  EXPECT(runtime.register_allocation_site_id(kSiteA, 1));
  EXPECT(runtime.register_allocation_site_id(kSiteB, 1));   // same type, other site
  EXPECT(runtime.register_allocation_site_id(kSiteOther, 2));
}

// 1. A workload that allocates and releases one object per step must not run
// out of arena: one million steps in a 4 KiB arena.
void steady_state_does_not_exhaust() {
  Runtime runtime(0x10000, 4096);
  set_up(runtime);
  unsigned long completed = 0;
  for (unsigned long i = 0; i < 1000000; ++i) {
    const uintptr_t p = runtime.allocate_from_site(100 + i % 50, kSiteA);
    if (!p) break;
    if (!runtime.release(p)) break;
    ++completed;
  }
  std::printf("steady state: %lu of 1000000 allocate/release steps completed\n", completed);
  EXPECT(completed == 1000000);
}

// 2. A released address goes to the next fitting allocation at the same site,
// and the record of the new object, not of the old one, bounds the check.
void same_site_reuses_and_bounds_follow_new_object() {
  Runtime runtime(0x10000, 4096);
  set_up(runtime);
  const uintptr_t old_object = runtime.allocate_from_site(64, kSiteA);
  EXPECT(old_object != 0);
  EXPECT(runtime.check(old_object, 64, kName) == CheckResult::ok);
  EXPECT(runtime.release(old_object));
  EXPECT(runtime.check(old_object, 1, kName) == CheckResult::untracked);

  const uintptr_t new_object = runtime.allocate_from_site(16, kSiteA);
  EXPECT(new_object == old_object);
  EXPECT(runtime.check(new_object, 16, kName) == CheckResult::ok);
  EXPECT(runtime.check(new_object, 17, kName) == CheckResult::out_of_bounds);
  EXPECT(runtime.check(new_object + 16, 1, kName) == CheckResult::untracked);
  size_t size = 0;
  EXPECT(runtime.allocation_size(new_object, size) && size == 16);
}

// 3. No other site gets the address: not a site of another type, and not
// another site of the same type.
void other_sites_do_not_reuse() {
  Runtime runtime(0x10000, 4096);
  set_up(runtime);
  const uintptr_t released = runtime.allocate_from_site(64, kSiteA);
  EXPECT(runtime.release(released));
  const uintptr_t other_type = runtime.allocate_from_site(64, kSiteOther);
  const uintptr_t same_type_other_site = runtime.allocate_from_site(64, kSiteB);
  EXPECT(other_type != 0 && other_type != released);
  EXPECT(same_type_other_site != 0 && same_type_other_site != released);
  // The stale pointer still matches no record.
  EXPECT(runtime.check(released, 1, kName) == CheckResult::untracked);
  EXPECT(runtime.check(released, 1, kOther) == CheckResult::untracked);
  // The original site still gets it back.
  EXPECT(runtime.allocate_from_site(64, kSiteA) == released);
}

// 4. A request larger than every released block of the site takes fresh
// arena, and the arena limit still holds.
void larger_request_takes_fresh_arena() {
  Runtime runtime(0x10000, 256);
  set_up(runtime);
  const uintptr_t small = runtime.allocate_from_site(32, kSiteA);
  EXPECT(runtime.release(small));
  const uintptr_t large = runtime.allocate_from_site(128, kSiteA);
  EXPECT(large != 0 && large != small);
  EXPECT(runtime.allocate_from_site(128, kSiteA) == 0);   // 32 + 128 used of 256
  EXPECT(runtime.allocate_from_site(32, kSiteA) == small);
}

// 5. Among several released blocks the smallest that fits is taken, so a
// small request does not consume the large block.
void smallest_fitting_block_is_taken() {
  Runtime runtime(0x10000, 4096);
  set_up(runtime);
  const uintptr_t large = runtime.allocate_from_site(256, kSiteA);
  const uintptr_t small = runtime.allocate_from_site(32, kSiteA);
  EXPECT(runtime.release(large));
  EXPECT(runtime.release(small));
  EXPECT(runtime.allocate_from_site(24, kSiteA) == small);
  EXPECT(runtime.allocate_from_site(200, kSiteA) == large);
}

// 6. Growing a buffer by reallocation, repeated many times, does not run out:
// the blocks of earlier rounds are reused.
void repeated_growth_does_not_exhaust() {
  Runtime runtime(0x10000, 4096);
  set_up(runtime);
  unsigned completed = 0;
  for (unsigned round = 0; round < 100000; ++round) {
    uintptr_t p = runtime.allocate_from_site(16, kSiteA);
    for (size_t size = 32; p && size <= 512; size *= 2) p = runtime.reallocate(p, size);
    if (!p || runtime.check(p, 512, kName) != CheckResult::ok || !runtime.release(p)) break;
    ++completed;
  }
  std::printf("repeated growth: %u of 100000 rounds completed\n", completed);
  EXPECT(completed == 100000);
}

// 7. A typed array that reuses a block has its own element layout.
void typed_array_reuse_has_fresh_layout() {
  Runtime runtime(0x10000, 4096);
  EXPECT(runtime.register_type(1, kName));
  EXPECT(runtime.register_type_layout(1, 12, 4));
  const uintptr_t first = runtime.allocate_typed_array(8, 1);
  EXPECT(first != 0);
  EXPECT(runtime.release(first));
  const uintptr_t second = runtime.allocate_typed_array(2, 1);
  EXPECT(second == first);
  EXPECT(runtime.check_typed_element(second + 12, 12, kName) == CheckResult::ok);
  EXPECT(runtime.check_typed_element(second + 24, 12, kName) != CheckResult::ok);
}

}  // namespace

int main() {
  steady_state_does_not_exhaust();
  same_site_reuses_and_bounds_follow_new_object();
  other_sites_do_not_reuse();
  larger_request_takes_fresh_arena();
  smallest_fitting_block_is_taken();
  repeated_growth_does_not_exhaust();
  typed_array_reuse_has_fresh_layout();
  if (failures) {
    std::printf("runtime_address_reuse: %d checks failed\n", failures);
    return 1;
  }
  std::printf("runtime_address_reuse: all checks passed\n");
  return 0;
}
