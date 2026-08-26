#include "interspec/runtime.h"
#include "interspec_popt_t_policy.h"

#include <cstdint>

extern "C" {
using popt_alloc_fn = uint32_t (*)(uint32_t, uint32_t);
void interspec_popt_init(popt_alloc_fn);
void* interspec_popt_parse_smoke();
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

  sandbox.destroy_sandbox();
}
