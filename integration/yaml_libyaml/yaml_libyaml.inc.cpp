#include "interspec/policy_runtime.h"
#include "interspec_yaml_t_policy.h"

#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

extern "C" {
void interspec_yaml_init(uint32_t);
void* interspec_yaml_make_scalar();
unsigned char* interspec_yaml_scalar_value(void*);
unsigned char* interspec_yaml_scalar_wrong_type();
unsigned char* interspec_yaml_scalar_untracked();
unsigned char* interspec_yaml_scalar_oversized(void*);
uint32_t interspec_yaml_scalar_size();
}

using YamlSandbox = rlbox::rlbox_sandbox<TestType>;

static interspec::PolicyRuntime* yaml_policy_runtime;

static rlbox::tainted<uint32_t, TestType> yaml_allocate(
  YamlSandbox& sandbox,
  rlbox::tainted<uint32_t, TestType> size)
{
  return static_cast<uint32_t>(
    yaml_policy_runtime->allocate_from_callback(
      *sandbox.get_sandbox_impl(), size.UNSAFE_unverified()));
}

TEST_CASE("InterSpec libyaml structured scalar generalization", "[yaml_libyaml]")
{
  using namespace interspec::yaml_libyaml_generated;
  constexpr uint32_t kArenaSize = 64 * 1024;

  YamlSandbox sandbox;
  CreateSandbox(sandbox);

  const uint32_t arena_base =
    sandbox.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
  REQUIRE(arena_base != 0);

  interspec::PolicyRuntime policy_runtime(arena_base, kArenaSize);
  yaml_policy_runtime = &policy_runtime;
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

  auto alloc_cb = sandbox.register_callback(yaml_allocate);
  const uint32_t alloc_slot = sandbox.get_sandbox_impl()->callback_slot_for_key(
    reinterpret_cast<const void*>(yaml_allocate));
  REQUIRE(alloc_slot != std::numeric_limits<uint32_t>::max());
  sandbox.invoke_sandbox_function(interspec_yaml_init, alloc_slot);

  /*
   * The event object remains U-owned. T does not dereference its nested pointer
   * fields directly; U exposes the scalar value and length, and T validates
   * that returned range before copying it.
   */
  auto event = sandbox.invoke_sandbox_function(interspec_yaml_make_scalar);
  REQUIRE(event.UNSAFE_unverified() != nullptr);

  auto value = sandbox.invoke_sandbox_function(interspec_yaml_scalar_value, event);
  REQUIRE(value.UNSAFE_unverified() != nullptr);
  const uint32_t value_bytes =
    sandbox.invoke_sandbox_function(interspec_yaml_scalar_size)
      .UNSAFE_unverified();
  REQUIRE(value_bytes == sizeof("InterSpec-yaml") - 1);

  const uintptr_t value_addr = sandbox.get_sandbox_impl()->sandbox_address(
    value.UNSAFE_unverified());
  const auto valid = checked_dynamic_access(
    runtime, value_addr, value_bytes, kUseYamlScalarValueRange);
  REQUIRE(valid.result == interspec::CheckResult::ok);
  REQUIRE(valid.address == value_addr);
  REQUIRE(valid.bytes == value_bytes);
  REQUIRE(runtime.check(value_addr, 1, kTypeHashYamlScalarValue) ==
          interspec::CheckResult::ok);

  std::vector<unsigned char> trusted(value_bytes + 1, 0);
  std::memcpy(trusted.data(), value.UNSAFE_unverified(), value_bytes);
  REQUIRE(std::strcmp(reinterpret_cast<const char*>(trusted.data()),
                      "InterSpec-yaml") == 0);

  auto wrong = sandbox.invoke_sandbox_function(
    interspec_yaml_scalar_wrong_type);
  REQUIRE(wrong.UNSAFE_unverified() != nullptr);
  const uint32_t wrong_bytes =
    sandbox.invoke_sandbox_function(interspec_yaml_scalar_size)
      .UNSAFE_unverified();
  const uintptr_t wrong_addr = sandbox.get_sandbox_impl()->sandbox_address(
    wrong.UNSAFE_unverified());
  REQUIRE(check_dynamic(runtime,
                        wrong_addr,
                        wrong_bytes,
                        kUseYamlScalarValueRange) ==
          interspec::CheckResult::wrong_type);

  auto untracked = sandbox.invoke_sandbox_function(
    interspec_yaml_scalar_untracked);
  REQUIRE(untracked.UNSAFE_unverified() != nullptr);
  const uint32_t untracked_bytes =
    sandbox.invoke_sandbox_function(interspec_yaml_scalar_size)
      .UNSAFE_unverified();
  const uintptr_t untracked_addr = sandbox.get_sandbox_impl()->sandbox_address(
    untracked.UNSAFE_unverified());
  REQUIRE(check_dynamic(runtime,
                        untracked_addr,
                        untracked_bytes,
                        kUseYamlScalarValueRange) ==
          interspec::CheckResult::untracked);

  auto oversized = sandbox.invoke_sandbox_function(
    interspec_yaml_scalar_oversized, event);
  REQUIRE(oversized.UNSAFE_unverified() != nullptr);
  const uint32_t oversized_bytes =
    sandbox.invoke_sandbox_function(interspec_yaml_scalar_size)
      .UNSAFE_unverified();
  const uintptr_t oversized_addr = sandbox.get_sandbox_impl()->sandbox_address(
    oversized.UNSAFE_unverified());
  REQUIRE(oversized_addr == value_addr);
  REQUIRE(oversized_bytes > value_bytes);
  REQUIRE(check_dynamic(runtime,
                        oversized_addr,
                        oversized_bytes,
                        kUseYamlScalarValueRange) ==
          interspec::CheckResult::out_of_bounds);

  sandbox.destroy_sandbox();
}
