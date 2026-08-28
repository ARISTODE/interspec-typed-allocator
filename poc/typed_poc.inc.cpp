#include "interspec/runtime.h"
#include "interspec_t_policy.h"

#include <cstdint>
#include <limits>

extern "C" {
using poc_free_fn = int (*)(uint32_t);
void typed_poc_init(uint32_t, poc_free_fn);
unsigned char* typed_poc_make_item();
unsigned char* typed_poc_make_other();
unsigned char* typed_poc_make_item_from_other_site();
unsigned char* typed_poc_try_unauthorized_site();
unsigned char* typed_poc_make_untracked();
int typed_poc_release(unsigned char*);
void typed_poc_release_untracked(unsigned char*);
int typed_poc_try_munmap(uint32_t, uint32_t);
int typed_poc_try_mprotect(uint32_t, uint32_t);
int typed_poc_try_remap(uint32_t, uint32_t);
}

using PocSandbox = rlbox::rlbox_sandbox<TestType>;

static interspec::Runtime* poc_runtime;

static rlbox::tainted<uint32_t, TestType> poc_allocate(
  PocSandbox& sandbox,
  rlbox::tainted<uint32_t, TestType> size)
{
  const uintptr_t pc =
    sandbox.get_sandbox_impl()->callback_program_counter();
  return static_cast<uint32_t>(
    poc_runtime->allocate_from_pc(size.UNSAFE_unverified(), pc));
}

static rlbox::tainted<int, TestType> poc_release(
  PocSandbox&,
  rlbox::tainted<uint32_t, TestType> ptr)
{
  return poc_runtime->release(ptr.UNSAFE_unverified());
}

TEST_CASE("InterSpec typed allocation PoC", "[typed_allocator]")
{
  using namespace interspec::generated;
  constexpr uint32_t kArenaSize = 64 * 1024;

  PocSandbox sandbox;
  CreateSandbox(sandbox);

  const uint32_t arena_base =
    sandbox.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
  REQUIRE(arena_base != 0);

  interspec::Runtime runtime(arena_base, kArenaSize);
  poc_runtime = &runtime;
  REQUIRE(register_types(runtime));
  REQUIRE(!runtime.register_type(kTypeIdItem, kTypeHashOther));

  auto resolve_symbol = [&](const char* name) -> uintptr_t {
    return sandbox.get_sandbox_impl()->lookup_symbol_address(name);
  };
  REQUIRE(register_allocation_sites(runtime, resolve_symbol));
  REQUIRE(runtime.allocation_site_count() == kAllocationSiteCount);
  REQUIRE(runtime.allocation_count() == 0);

  auto alloc_cb = sandbox.register_callback(poc_allocate);
  auto free_cb = sandbox.register_callback(poc_release);
  const uint32_t alloc_slot = sandbox.get_sandbox_impl()->callback_slot_for_key(
    reinterpret_cast<const void*>(poc_allocate));
  REQUIRE(alloc_slot != std::numeric_limits<uint32_t>::max());
  sandbox.invoke_sandbox_function(typed_poc_init, alloc_slot, free_cb);

  /* These ordinary malloc sites are rewritten from inferred allocation policy. */
  auto item = sandbox.invoke_sandbox_function(typed_poc_make_item);
  REQUIRE(item.UNSAFE_unverified() != nullptr);
  REQUIRE(runtime.allocation_count() == 1);

  auto other = sandbox.invoke_sandbox_function(typed_poc_make_other);
  REQUIRE(other.UNSAFE_unverified() != nullptr);
  REQUIRE(runtime.allocation_count() == 2);

  auto wrong_site =
    sandbox.invoke_sandbox_function(typed_poc_make_item_from_other_site);
  REQUIRE(wrong_site.UNSAFE_unverified() != nullptr);
  REQUIRE(runtime.allocation_count() == 3);

  /* P7a: calling the allocator syscall from a non-authorized U instruction is
   * rejected even though U knows which callback slot performs allocation. */
  auto unauthorized =
    sandbox.invoke_sandbox_function(typed_poc_try_unauthorized_site);
  REQUIRE(unauthorized.UNSAFE_unverified() == nullptr);
  REQUIRE(runtime.allocation_count() == 3);

  auto untracked = sandbox.invoke_sandbox_function(typed_poc_make_untracked);
  REQUIRE(runtime.allocation_count() == 3);

  const uintptr_t item_ptr =
    sandbox.get_sandbox_impl()->sandbox_address(item.UNSAFE_unverified());
  const uintptr_t other_ptr =
    sandbox.get_sandbox_impl()->sandbox_address(other.UNSAFE_unverified());
  const uintptr_t wrong_site_ptr =
    sandbox.get_sandbox_impl()->sandbox_address(wrong_site.UNSAFE_unverified());
  const uintptr_t untracked_ptr =
    sandbox.get_sandbox_impl()->sandbox_address(untracked.UNSAFE_unverified());

  interspec::SiteId item_site = 0;
  interspec::SiteId other_site = 0;
  interspec::SiteId wrong_site_id = 0;
  REQUIRE(runtime.allocation_site(item_ptr, item_site));
  REQUIRE(runtime.allocation_site(other_ptr, other_site));
  REQUIRE(runtime.allocation_site(wrong_site_ptr, wrong_site_id));
  REQUIRE(item_site == kAllocationSites[0].site_id);
  REQUIRE(other_site == kAllocationSites[1].site_id);
  REQUIRE(wrong_site_id == other_site);

  /* T uses consume inferred expected-type and field access-range policy. */
  REQUIRE(check(runtime, item_ptr, kUseItemValue) == interspec::CheckResult::ok);
  const auto value_access = checked_access(runtime, item_ptr, kUseItemValue);
  REQUIRE(value_access.result == interspec::CheckResult::ok);
  REQUIRE(value_access.address == item_ptr + 4);
  REQUIRE(value_access.bytes == 4);
  REQUIRE(check(runtime, other_ptr, kUseItemValue) ==
          interspec::CheckResult::wrong_type);

  /* U wrote Item-shaped bytes, but T still records the trusted Other label. */
  REQUIRE(check(runtime, wrong_site_ptr, kUseItemValue) ==
          interspec::CheckResult::wrong_type);
  REQUIRE(check(runtime, wrong_site_ptr, kUseOtherValue) ==
          interspec::CheckResult::ok);

  REQUIRE(runtime.check(item_ptr, 9, kTypeHashItem) ==
          interspec::CheckResult::out_of_bounds);
  REQUIRE(runtime.check(item_ptr + 4, 5, kTypeHashItem) ==
          interspec::CheckResult::out_of_bounds);
  REQUIRE(runtime.check(untracked_ptr, 8, kTypeHashItem) ==
          interspec::CheckResult::untracked);

  REQUIRE(sandbox.invoke_sandbox_function(typed_poc_try_munmap,
                                          arena_base,
                                          kArenaSize)
            .UNSAFE_unverified() == -1);
  REQUIRE(sandbox.invoke_sandbox_function(typed_poc_try_mprotect,
                                          arena_base,
                                          kArenaSize)
            .UNSAFE_unverified() == -1);
  REQUIRE(sandbox.invoke_sandbox_function(typed_poc_try_remap,
                                          arena_base,
                                          kArenaSize)
            .UNSAFE_unverified() == -1);
  REQUIRE(check(runtime, item_ptr, kUseItemValue) == interspec::CheckResult::ok);

  REQUIRE(sandbox.invoke_sandbox_function(typed_poc_release, item)
            .UNSAFE_unverified() == 1);
  REQUIRE(runtime.allocation_count() == 2);
  REQUIRE(check(runtime, item_ptr, kUseItemValue) ==
          interspec::CheckResult::untracked);

  sandbox.invoke_sandbox_function(typed_poc_release_untracked, untracked);
  sandbox.destroy_sandbox();
}
