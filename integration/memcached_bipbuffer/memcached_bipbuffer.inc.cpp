#include "interspec/policy_runtime.h"
#include "interspec_bipbuffer_t_policy.h"

#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

extern "C" {
void interspec_bipbuf_init(uint32_t);
void* interspec_bipbuf_make_and_fill();
unsigned char* interspec_bipbuf_peek_valid(void*);
unsigned char* interspec_bipbuf_peek_wrong_type();
unsigned char* interspec_bipbuf_peek_untracked();
unsigned char* interspec_bipbuf_peek_oversized(void*);
uint32_t interspec_bipbuf_last_size();
}

using BipbufSandbox = rlbox::rlbox_sandbox<TestType>;

static interspec::PolicyRuntime* bipbuf_policy_runtime;

static rlbox::tainted<uint32_t, TestType> bipbuf_allocate(
  BipbufSandbox& sandbox,
  rlbox::tainted<uint32_t, TestType> size)
{
  return static_cast<uint32_t>(
    bipbuf_policy_runtime->allocate_from_callback(
      *sandbox.get_sandbox_impl(), size.UNSAFE_unverified()));
}

TEST_CASE("InterSpec memcached bipbuffer generalization", "[memcached_bipbuffer]")
{
  using namespace interspec::memcached_bipbuffer_generated;
  constexpr uint32_t kArenaSize = 64 * 1024;

  BipbufSandbox sandbox;
  CreateSandbox(sandbox);

  const auto domain_range_ok = [&](const void* ptr, size_t bytes) {
    if (ptr == nullptr || bytes == 0) return false;
    const uintptr_t start = reinterpret_cast<uintptr_t>(ptr);
    if (start > std::numeric_limits<uintptr_t>::max() - (bytes - 1)) return false;
    const void* end = reinterpret_cast<const void*>(start + bytes - 1);
    return sandbox.is_pointer_in_sandbox_memory(ptr) &&
           sandbox.is_pointer_in_sandbox_memory(end);
  };

  const uint32_t arena_base =
    sandbox.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
  REQUIRE(arena_base != 0);

  interspec::PolicyRuntime policy_runtime(arena_base, kArenaSize);
  bipbuf_policy_runtime = &policy_runtime;
  REQUIRE(policy_runtime.initialize_from_sandbox(
    *sandbox.get_sandbox_impl(),
    [](interspec::Runtime& runtime) { return register_types(runtime); },
    [](interspec::Runtime& runtime, auto resolve) {
      return register_allocation_policy(runtime, resolve);
    }));

  interspec::Runtime& runtime = policy_runtime.runtime();
  REQUIRE(runtime.allocation_site_count() == kTotalAllocationSiteCount);
  REQUIRE(kAllocationSiteCount == 1);
  REQUIRE(kHelperAllocationSiteCount == 1);
  REQUIRE(kDynamicUseCount == 1);

  auto alloc_cb = sandbox.register_callback(bipbuf_allocate);
  const uint32_t alloc_slot = sandbox.get_sandbox_impl()->callback_slot_for_key(
    reinterpret_cast<const void*>(bipbuf_allocate));
  REQUIRE(alloc_slot != std::numeric_limits<uint32_t>::max());
  sandbox.invoke_sandbox_function(interspec_bipbuf_init, alloc_slot);

  auto owner = sandbox.invoke_sandbox_function(interspec_bipbuf_make_and_fill);
  REQUIRE(owner.UNSAFE_unverified() != nullptr);
  REQUIRE(runtime.allocation_count() == 1);

  const uintptr_t owner_addr = sandbox.get_sandbox_impl()->sandbox_address(
    owner.UNSAFE_unverified());
  REQUIRE(runtime.check(owner_addr, 1, kTypeHashBipbufT) ==
          interspec::CheckResult::ok);

  auto valid = sandbox.invoke_sandbox_function(interspec_bipbuf_peek_valid, owner);
  REQUIRE(valid.UNSAFE_unverified() != nullptr);
  const uint32_t valid_len =
    sandbox.invoke_sandbox_function(interspec_bipbuf_last_size).UNSAFE_unverified();
  REQUIRE(valid_len == sizeof("InterSpec-bipbuffer"));
  REQUIRE(domain_range_ok(valid.UNSAFE_unverified(), valid_len));

  const uintptr_t valid_addr = sandbox.get_sandbox_impl()->sandbox_address(
    valid.UNSAFE_unverified());
  REQUIRE(valid_addr > owner_addr);
  const auto valid_access = checked_dynamic_access(
    runtime, valid_addr, valid_len, kUseBipbufPeekAllRange);
  REQUIRE(valid_access.result == interspec::CheckResult::ok);
  REQUIRE(valid_access.address == valid_addr);
  REQUIRE(valid_access.bytes == valid_len);

  std::vector<unsigned char> trusted(valid_len);
  std::memcpy(trusted.data(), valid.UNSAFE_unverified(), valid_len);
  REQUIRE(std::strcmp(reinterpret_cast<const char*>(trusted.data()),
                      "InterSpec-bipbuffer") == 0);

  /* Original domain/range SP3 accepts this tracked same-domain range. */
  auto wrong = sandbox.invoke_sandbox_function(interspec_bipbuf_peek_wrong_type);
  REQUIRE(wrong.UNSAFE_unverified() != nullptr);
  const uint32_t wrong_len =
    sandbox.invoke_sandbox_function(interspec_bipbuf_last_size).UNSAFE_unverified();
  REQUIRE(domain_range_ok(wrong.UNSAFE_unverified(), wrong_len));
  const uintptr_t wrong_addr = sandbox.get_sandbox_impl()->sandbox_address(
    wrong.UNSAFE_unverified());
  REQUIRE(check_dynamic(runtime, wrong_addr, wrong_len, kUseBipbufPeekAllRange) ==
          interspec::CheckResult::wrong_type);

  /* Ordinary malloc is also in U and passes domain/range validation. */
  auto untracked = sandbox.invoke_sandbox_function(interspec_bipbuf_peek_untracked);
  REQUIRE(untracked.UNSAFE_unverified() != nullptr);
  const uint32_t untracked_len =
    sandbox.invoke_sandbox_function(interspec_bipbuf_last_size).UNSAFE_unverified();
  REQUIRE(domain_range_ok(untracked.UNSAFE_unverified(), untracked_len));
  const uintptr_t untracked_addr = sandbox.get_sandbox_impl()->sandbox_address(
    untracked.UNSAFE_unverified());
  REQUIRE(check_dynamic(runtime,
                        untracked_addr,
                        untracked_len,
                        kUseBipbufPeekAllRange) ==
          interspec::CheckResult::untracked);

  /* Corrupted extent remains in sandbox memory but escapes the owning object. */
  auto oversized = sandbox.invoke_sandbox_function(
    interspec_bipbuf_peek_oversized, owner);
  REQUIRE(oversized.UNSAFE_unverified() != nullptr);
  const uint32_t oversized_len =
    sandbox.invoke_sandbox_function(interspec_bipbuf_last_size).UNSAFE_unverified();
  REQUIRE(domain_range_ok(oversized.UNSAFE_unverified(), oversized_len));
  const uintptr_t oversized_addr = sandbox.get_sandbox_impl()->sandbox_address(
    oversized.UNSAFE_unverified());
  REQUIRE(oversized_addr == valid_addr);
  REQUIRE(oversized_len > valid_len);
  REQUIRE(check_dynamic(runtime,
                        oversized_addr,
                        oversized_len,
                        kUseBipbufPeekAllRange) ==
          interspec::CheckResult::out_of_bounds);

  sandbox.destroy_sandbox();
}
