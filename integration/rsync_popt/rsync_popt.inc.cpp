#include "interspec/runtime.h"
#include "interspec_popt_t_policy.h"

#include <cstdint>
#include <cstring>
#include <vector>

extern "C" {
using popt_alloc_fn = uint32_t (*)(uint32_t, uint32_t);
void interspec_popt_init(popt_alloc_fn);
void* interspec_popt_parse_smoke();
char* interspec_popt_get_opt_arg(void*);
int interspec_popt_archive_seen();
}

using PoptSandbox = rlbox::rlbox_sandbox<TestType>;

static interspec::Runtime* popt_runtime;

static rlbox::tainted<uint32_t, TestType> popt_allocate(
  PoptSandbox&,
  rlbox::tainted<uint32_t, TestType> size,
  rlbox::tainted<uint32_t, TestType> type_id)
{
  return static_cast<uint32_t>(
    popt_runtime->allocate(size.UNSAFE_unverified(), type_id.UNSAFE_unverified()));
}

TEST_CASE("InterSpec real rsync popt integration", "[rsync_popt]")
{
  using namespace interspec::rsync_popt_generated;
  constexpr uint32_t kArenaSize = 64 * 1024;

  PoptSandbox sandbox;
  CreateSandbox(sandbox);

  const uint32_t arena_base =
    sandbox.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
  REQUIRE(arena_base != 0);

  interspec::Runtime runtime(arena_base, kArenaSize);
  popt_runtime = &runtime;
  REQUIRE(register_types(runtime));

  auto alloc_cb = sandbox.register_callback(popt_allocate);
  sandbox.invoke_sandbox_function(interspec_popt_init, alloc_cb);

  auto ctx = sandbox.invoke_sandbox_function(interspec_popt_parse_smoke);
  REQUIRE(ctx.UNSAFE_unverified() != nullptr);
  REQUIRE(sandbox.invoke_sandbox_function(interspec_popt_archive_seen)
            .UNSAFE_unverified() == 1);
  REQUIRE(runtime.allocation_count() == 1);

  const uintptr_t ctx_ptr =
    sandbox.get_sandbox_impl()->sandbox_address(ctx.UNSAFE_unverified());
  REQUIRE(runtime.check(ctx_ptr, 1, kTypeHashPoptContextS) ==
          interspec::CheckResult::ok);

  auto arg = sandbox.invoke_sandbox_function(interspec_popt_get_opt_arg, ctx);
  REQUIRE(arg.UNSAFE_unverified() != nullptr);
  REQUIRE(runtime.allocation_count() == 2);

  const uintptr_t arg_ptr =
    sandbox.get_sandbox_impl()->sandbox_address(arg.UNSAFE_unverified());
  size_t arg_bytes = 0;
  REQUIRE(runtime.remaining_bytes(arg_ptr, kTypeHashChar, arg_bytes) ==
          interspec::CheckResult::ok);
  REQUIRE(arg_bytes == sizeof("destination"));

  std::vector<char> trusted_copy(arg_bytes);
  std::memcpy(trusted_copy.data(), arg.UNSAFE_unverified(), arg_bytes);
  REQUIRE(trusted_copy.back() == '\0');
  REQUIRE(std::strcmp(trusted_copy.data(), "destination") == 0);

  sandbox.destroy_sandbox();
}
