#include "interspec/runtime.h"

#include <cstdint>

extern "C" {
using poc_alloc_fn = uint32_t (*)(uint32_t, uint32_t);
using poc_free_fn = int (*)(uint32_t);
void typed_poc_init(poc_alloc_fn, poc_free_fn);
unsigned char* typed_poc_make_item();
unsigned char* typed_poc_make_other();
unsigned char* typed_poc_make_item_from_other_site();
unsigned char* typed_poc_try_unknown_type();
unsigned char* typed_poc_make_untracked();
int typed_poc_release(unsigned char*);
void typed_poc_release_untracked(unsigned char*);
int typed_poc_try_munmap(uint32_t, uint32_t);
int typed_poc_try_mprotect(uint32_t, uint32_t);
int typed_poc_try_remap(uint32_t, uint32_t);
}

using PocSandbox = rlbox::rlbox_sandbox<TestType>;

static constexpr uint64_t kItemType = interspec::type_hash("Item");
static constexpr uint64_t kOtherType = interspec::type_hash("Other");
static constexpr interspec::TypeId kItemTypeId = 1;
static constexpr interspec::TypeId kOtherTypeId = 2;
static interspec::Runtime* poc_runtime;

static rlbox::tainted<uint32_t, TestType> poc_allocate(
  PocSandbox&,
  rlbox::tainted<uint32_t, TestType> size,
  rlbox::tainted<uint32_t, TestType> type_id)
{
  return static_cast<uint32_t>(
    poc_runtime->allocate(size.UNSAFE_unverified(), type_id.UNSAFE_unverified()));
}

static rlbox::tainted<int, TestType> poc_release(
  PocSandbox&,
  rlbox::tainted<uint32_t, TestType> ptr)
{
  return poc_runtime->release(ptr.UNSAFE_unverified());
}

TEST_CASE("InterSpec typed allocation PoC", "[typed_allocator]")
{
  constexpr uint32_t kArenaSize = 64 * 1024;

  PocSandbox sandbox;
  CreateSandbox(sandbox);

  const uint32_t arena_base =
    sandbox.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
  REQUIRE(arena_base != 0);

  interspec::Runtime runtime(arena_base, kArenaSize);
  poc_runtime = &runtime;
  REQUIRE(runtime.register_type(kItemTypeId, kItemType));
  REQUIRE(runtime.register_type(kOtherTypeId, kOtherType));
  REQUIRE_FALSE(runtime.register_type(kItemTypeId, kOtherType));
  REQUIRE(runtime.allocation_count() == 0);

  auto alloc_cb = sandbox.register_callback(poc_allocate);
  auto free_cb = sandbox.register_callback(poc_release);
  sandbox.invoke_sandbox_function(typed_poc_init, alloc_cb, free_cb);

  auto item = sandbox.invoke_sandbox_function(typed_poc_make_item);
  REQUIRE(runtime.allocation_count() == 1);

  auto other = sandbox.invoke_sandbox_function(typed_poc_make_other);
  REQUIRE(runtime.allocation_count() == 2);

  auto wrong_site =
    sandbox.invoke_sandbox_function(typed_poc_make_item_from_other_site);
  REQUIRE(runtime.allocation_count() == 3);

  auto unknown = sandbox.invoke_sandbox_function(typed_poc_try_unknown_type);
  REQUIRE(unknown.UNSAFE_unverified() == nullptr);
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

  REQUIRE(runtime.check(item_ptr, 8, kItemType) == interspec::CheckResult::ok);
  REQUIRE(runtime.check(other_ptr, 8, kItemType) ==
          interspec::CheckResult::wrong_type);

  /* U wrote Item-shaped bytes, but T still records the trusted Other label. */
  REQUIRE(runtime.check(wrong_site_ptr, 8, kItemType) ==
          interspec::CheckResult::wrong_type);
  REQUIRE(runtime.check(wrong_site_ptr, 8, kOtherType) ==
          interspec::CheckResult::ok);

  REQUIRE(runtime.check(item_ptr, 9, kItemType) ==
          interspec::CheckResult::out_of_bounds);
  REQUIRE(runtime.check(item_ptr + 4, 4, kItemType) ==
          interspec::CheckResult::ok);
  REQUIRE(runtime.check(item_ptr + 4, 5, kItemType) ==
          interspec::CheckResult::out_of_bounds);
  REQUIRE(runtime.check(untracked_ptr, 8, kItemType) ==
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
  REQUIRE(runtime.check(item_ptr, 8, kItemType) == interspec::CheckResult::ok);

  REQUIRE(sandbox.invoke_sandbox_function(typed_poc_release, item)
            .UNSAFE_unverified() == 1);
  REQUIRE(runtime.allocation_count() == 2);
  REQUIRE(runtime.check(item_ptr, 8, kItemType) ==
          interspec::CheckResult::untracked);

  sandbox.invoke_sandbox_function(typed_poc_release_untracked, untracked);
  sandbox.destroy_sandbox();
}
