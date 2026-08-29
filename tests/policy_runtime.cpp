#include "interspec/policy_runtime.h"

#include <cassert>
#include <cstdint>
#include <cstring>

namespace {

constexpr interspec::TypeId kTypeId = 1;
constexpr interspec::SiteId kSiteId = 7;
constexpr uint64_t kTypeHash = UINT64_C(0x123456789abcdef0);

struct FakeSandboxImpl {
  uintptr_t begin = 0x200;
  uintptr_t end = 0x210;
  uintptr_t pc = 0;
  uintptr_t next_pc = 0;

  uintptr_t lookup_symbol_address(const char* name) {
    if (std::strcmp(name, "site_begin") == 0) return begin;
    if (std::strcmp(name, "site_end") == 0) return end;
    return 0;
  }

  uintptr_t callback_program_counter() const { return pc; }
  uintptr_t callback_new_program_counter() const { return next_pc; }
};

bool register_types(interspec::Runtime& runtime) {
  return runtime.register_type(kTypeId, kTypeHash);
}

template <typename Resolver>
bool register_sites(interspec::Runtime& runtime, Resolver resolve) {
  return runtime.register_allocation_site(
      kSiteId, resolve("site_begin"), resolve("site_end"), kTypeId);
}

}  // namespace

int main() {
  constexpr uintptr_t kArenaBase = 0x100000;
  constexpr size_t kArenaSize = 4096;

  FakeSandboxImpl sandbox;
  interspec::PolicyRuntime policy(kArenaBase, kArenaSize);

  assert(policy.initialize_from_sandbox(
      sandbox,
      [](interspec::Runtime& runtime) { return register_types(runtime); },
      [](interspec::Runtime& runtime, auto resolve) {
        return register_sites(runtime, resolve);
      }));
  assert(policy.runtime().allocation_site_count() == 1);

  sandbox.pc = 0x204;
  uintptr_t first = policy.allocate_from_callback(sandbox, 16);
  assert(first == kArenaBase);
  assert(policy.runtime().check(first, 16, kTypeHash) ==
         interspec::CheckResult::ok);
  interspec::SiteId site_id = 0;
  assert(policy.runtime().allocation_site(first, site_id));
  assert(site_id == kSiteId);

  /* An allocator callback from an unregistered U instruction fails closed. */
  sandbox.pc = 0x300;
  sandbox.next_pc = 0;
  assert(policy.allocate_from_callback(sandbox, 16) == 0);
  assert(policy.runtime().allocation_count() == 1);

  /* Compatible backends may expose the authoritative return PC separately. */
  sandbox.pc = 0x300;
  sandbox.next_pc = 0x208;
  uintptr_t second = policy.allocate_from_callback(sandbox, 8);
  assert(second != 0);
  assert(policy.runtime().check(second, 8, kTypeHash) ==
         interspec::CheckResult::ok);

  return 0;
}
