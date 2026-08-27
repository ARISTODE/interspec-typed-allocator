#include <interspec/runtime.h>

#include <cstdint>
#include <iostream>
#include <string>

namespace {

using interspec::CheckResult;
using interspec::Runtime;
using interspec::TypeId;
using interspec::type_hash;

const char* result_name(CheckResult result) {
  switch (result) {
    case CheckResult::ok:
      return "ok";
    case CheckResult::untracked:
      return "untracked";
    case CheckResult::wrong_type:
      return "wrong_type";
    case CheckResult::out_of_bounds:
      return "out_of_bounds";
  }
  return "unknown";
}

bool report_check(const char* name, CheckResult expected, CheckResult actual) {
  const bool pass = expected == actual;
  std::cout << name << ',' << result_name(expected) << ',' << result_name(actual)
            << ',' << (pass ? "pass" : "fail") << '\n';
  return pass;
}

bool report_bool(const char* name, bool expected, bool actual) {
  const bool pass = expected == actual;
  std::cout << name << ',' << (expected ? "true" : "false") << ','
            << (actual ? "true" : "false") << ','
            << (pass ? "pass" : "fail") << '\n';
  return pass;
}

}  // namespace

int main() {
  constexpr uintptr_t kBase = 0x40000000;
  constexpr size_t kCapacity = 1u << 20;
  constexpr TypeId kItemId = 1;
  constexpr TypeId kOtherId = 2;
  constexpr TypeId kCollisionId = 3;
  constexpr uint64_t kItem = type_hash("Item");
  constexpr uint64_t kOther = type_hash("Other");

  bool all_pass = true;
  std::cout << "case,expected,actual,result\n";

  Runtime runtime(kBase, kCapacity);
  all_pass &= report_bool("register_item", true,
                          runtime.register_type(kItemId, kItem));
  all_pass &= report_bool("register_other", true,
                          runtime.register_type(kOtherId, kOther));
  all_pass &= report_bool("reject_typehash_collision", false,
                          runtime.register_type(kCollisionId, kItem));

  const uintptr_t item = runtime.allocate(32, kItemId);
  const uintptr_t other = runtime.allocate(32, kOtherId);
  all_pass &= report_bool("tracked_item_allocation", true, item != 0);
  all_pass &= report_bool("tracked_other_allocation", true, other != 0);
  all_pass &= report_bool("reject_unknown_typeid", true,
                          runtime.allocate(32, 999) == 0);
  all_pass &= report_bool("reject_zero_size", true,
                          runtime.allocate(0, kItemId) == 0);

  all_pass &= report_check("correct_type", CheckResult::ok,
                           runtime.check(item, 8, kItem));
  all_pass &= report_check("interior_pointer", CheckResult::ok,
                           runtime.check(item + 8, 8, kItem));
  all_pass &= report_check("wrong_type", CheckResult::wrong_type,
                           runtime.check(other, 8, kItem));
  all_pass &= report_check("cross_allocation_bound", CheckResult::out_of_bounds,
                           runtime.check(item + 24, 16, kItem));
  all_pass &= report_check("untracked_pointer", CheckResult::untracked,
                           runtime.check(kBase + kCapacity + 64, 8, kItem));

  all_pass &= report_bool("reject_interior_release", false,
                          runtime.release(item + 8));
  all_pass &= report_bool("release_exact_base", true, runtime.release(item));
  all_pass &= report_check("stale_after_free", CheckResult::untracked,
                           runtime.check(item, 8, kItem));

  const uintptr_t old_other = other;
  const uintptr_t resized_other = runtime.reallocate(old_other, 64);
  all_pass &= report_bool("realloc_success", true, resized_other != 0);
  all_pass &= report_check("stale_after_realloc", CheckResult::untracked,
                           runtime.check(old_other, 8, kOther));
  all_pass &= report_check("realloc_preserves_type", CheckResult::ok,
                           runtime.check(resized_other, 64, kOther));

  Runtime constrained(0x50000000, 64);
  all_pass &= report_bool("constrained_register", true,
                          constrained.register_type(kItemId, kItem));
  const uintptr_t constrained_item = constrained.allocate(48, kItemId);
  all_pass &= report_bool("constrained_allocate", true,
                          constrained_item != 0);
  all_pass &= report_bool("realloc_failure", true,
                          constrained.reallocate(constrained_item, 64) == 0);
  all_pass &= report_check("realloc_failure_keeps_old_live", CheckResult::ok,
                           constrained.check(constrained_item, 48, kItem));

  Runtime invalid(UINTPTR_MAX - 7, 64);
  all_pass &= report_bool("invalid_arena_detected", false,
                          invalid.arena_valid());
  all_pass &= report_bool("invalid_arena_allocation_rejected", true,
                          invalid.allocate(8, kItemId) == 0);

  return all_pass ? 0 : 1;
}
