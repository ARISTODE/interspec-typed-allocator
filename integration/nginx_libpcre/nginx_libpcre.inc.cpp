#include "interspec/policy_runtime.h"
#include "interspec_pcre_t_policy.h"

#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

extern "C" {
void interspec_pcre_init(uint32_t);
void* interspec_pcre_compile_named();
unsigned char* interspec_pcre_name_table(void*);
unsigned char* interspec_pcre_name_table_wrong_type();
unsigned char* interspec_pcre_name_table_untracked();
unsigned char* interspec_pcre_name_table_oversized(void*);
uint32_t interspec_pcre_name_table_size();
}

using PcreSandbox = rlbox::rlbox_sandbox<TestType>;

static interspec::PolicyRuntime* pcre_policy_runtime;

static rlbox::tainted<uint32_t, TestType> pcre_allocate(
  PcreSandbox& sandbox,
  rlbox::tainted<uint32_t, TestType> size)
{
  return static_cast<uint32_t>(
    pcre_policy_runtime->allocate_from_callback(
      *sandbox.get_sandbox_impl(), size.UNSAFE_unverified()));
}

TEST_CASE("InterSpec nginx libpcre name-table generalization", "[nginx_libpcre]")
{
  using namespace interspec::nginx_libpcre_generated;
  constexpr uint32_t kArenaSize = 128 * 1024;

  PcreSandbox sandbox;
  CreateSandbox(sandbox);

  const uint32_t arena_base =
    sandbox.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
  REQUIRE(arena_base != 0);

  interspec::PolicyRuntime policy_runtime(arena_base, kArenaSize);
  pcre_policy_runtime = &policy_runtime;
  REQUIRE(policy_runtime.initialize_from_sandbox(
    *sandbox.get_sandbox_impl(),
    [](interspec::Runtime& runtime) { return register_types(runtime); },
    [](interspec::Runtime& runtime, auto resolve) {
      return register_allocation_policy(runtime, resolve);
    }));

  interspec::Runtime& runtime = policy_runtime.runtime();
  REQUIRE(kAllocationSiteCount == 0);
  REQUIRE(kHelperAllocationSiteCount == 2);
  REQUIRE(kDynamicUseCount == 1);
  REQUIRE(runtime.allocation_site_count() == kTotalAllocationSiteCount);

  auto alloc_cb = sandbox.register_callback(pcre_allocate);
  const uint32_t alloc_slot = sandbox.get_sandbox_impl()->callback_slot_for_key(
    reinterpret_cast<const void*>(pcre_allocate));
  REQUIRE(alloc_slot != std::numeric_limits<uint32_t>::max());
  sandbox.invoke_sandbox_function(interspec_pcre_init, alloc_slot);

  /* The patched real PCRE compile allocation is an explicitly declared site. */
  auto compiled = sandbox.invoke_sandbox_function(interspec_pcre_compile_named);
  REQUIRE(compiled.UNSAFE_unverified() != nullptr);
  const uintptr_t compiled_addr = sandbox.get_sandbox_impl()->sandbox_address(
    compiled.UNSAFE_unverified());
  REQUIRE(runtime.check(compiled_addr, 1, kTypeHashRealPcre8Or16) ==
          interspec::CheckResult::ok);

  auto table = sandbox.invoke_sandbox_function(
    interspec_pcre_name_table, compiled);
  REQUIRE(table.UNSAFE_unverified() != nullptr);
  const uint32_t table_bytes =
    sandbox.invoke_sandbox_function(interspec_pcre_name_table_size)
      .UNSAFE_unverified();
  REQUIRE(table_bytes >= 7);

  const uintptr_t table_addr = sandbox.get_sandbox_impl()->sandbox_address(
    table.UNSAFE_unverified());
  REQUIRE(table_addr > compiled_addr);
  const auto valid = checked_dynamic_access(
    runtime, table_addr, table_bytes, kUsePcreNameTableRange);
  REQUIRE(valid.result == interspec::CheckResult::ok);
  REQUIRE(valid.address == table_addr);
  REQUIRE(valid.bytes == table_bytes);

  std::vector<unsigned char> trusted(table_bytes);
  std::memcpy(trusted.data(), table.UNSAFE_unverified(), table_bytes);
  REQUIRE(std::memcmp(trusted.data() + 2, "word", 4) == 0);

  /* Tracked same-domain memory of another trusted type is rejected. */
  auto wrong = sandbox.invoke_sandbox_function(
    interspec_pcre_name_table_wrong_type);
  REQUIRE(wrong.UNSAFE_unverified() != nullptr);
  const uint32_t wrong_bytes =
    sandbox.invoke_sandbox_function(interspec_pcre_name_table_size)
      .UNSAFE_unverified();
  const uintptr_t wrong_addr = sandbox.get_sandbox_impl()->sandbox_address(
    wrong.UNSAFE_unverified());
  REQUIRE(check_dynamic(runtime,
                        wrong_addr,
                        wrong_bytes,
                        kUsePcreNameTableRange) ==
          interspec::CheckResult::wrong_type);

  /* Ordinary sandbox malloc is same-domain but has no authoritative record. */
  auto untracked = sandbox.invoke_sandbox_function(
    interspec_pcre_name_table_untracked);
  REQUIRE(untracked.UNSAFE_unverified() != nullptr);
  const uint32_t untracked_bytes =
    sandbox.invoke_sandbox_function(interspec_pcre_name_table_size)
      .UNSAFE_unverified();
  const uintptr_t untracked_addr = sandbox.get_sandbox_impl()->sandbox_address(
    untracked.UNSAFE_unverified());
  REQUIRE(check_dynamic(runtime,
                        untracked_addr,
                        untracked_bytes,
                        kUsePcreNameTableRange) ==
          interspec::CheckResult::untracked);

  /* Correct interior pointer with a corrupted byte extent must fail spatially. */
  auto oversized = sandbox.invoke_sandbox_function(
    interspec_pcre_name_table_oversized, compiled);
  REQUIRE(oversized.UNSAFE_unverified() != nullptr);
  const uint32_t oversized_bytes =
    sandbox.invoke_sandbox_function(interspec_pcre_name_table_size)
      .UNSAFE_unverified();
  const uintptr_t oversized_addr = sandbox.get_sandbox_impl()->sandbox_address(
    oversized.UNSAFE_unverified());
  REQUIRE(oversized_addr == table_addr);
  REQUIRE(oversized_bytes > table_bytes);
  REQUIRE(check_dynamic(runtime,
                        oversized_addr,
                        oversized_bytes,
                        kUsePcreNameTableRange) ==
          interspec::CheckResult::out_of_bounds);

  sandbox.destroy_sandbox();
}
