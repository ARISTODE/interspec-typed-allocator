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
char* interspec_popt_get_opt_arg_wrong_type(void*);
char* interspec_popt_get_opt_arg_untracked(void*);
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

template<typename TaintedPtr>
static bool popt_copy_checked_cstring(PoptSandbox& sandbox,
                                      const interspec::Runtime& runtime,
                                      TaintedPtr arg,
                                      std::vector<char>& trusted_copy)
{
  using namespace interspec::rsync_popt_generated;

  auto raw = arg.UNSAFE_unverified();
  if (raw == nullptr) return false;

  const uintptr_t arg_ptr = sandbox.get_sandbox_impl()->sandbox_address(raw);

  /* Generated trusted-use policy establishes the expected allocated type
   * before T performs any dereference of the returned pointer. */
  if (check(runtime, arg_ptr, kUsePoptOptArgFirstByte) !=
      interspec::CheckResult::ok) {
    return false;
  }

  size_t arg_bytes = 0;
  if (runtime.remaining_bytes(arg_ptr, kTypeHashChar, arg_bytes) !=
        interspec::CheckResult::ok ||
      arg_bytes == 0) {
    return false;
  }

  trusted_copy.resize(arg_bytes);
  std::memcpy(trusted_copy.data(), raw, arg_bytes);

  /* A C-string consumer may scan up to the end of the tracked allocation.
   * Require termination inside that trusted bound before exposing the copy. */
  return trusted_copy.back() == '\0';
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

  std::vector<char> trusted_copy;
  REQUIRE(popt_copy_checked_cstring(sandbox, runtime, arg, trusted_copy));
  REQUIRE(trusted_copy.size() == sizeof("destination"));
  REQUIRE(std::strcmp(trusted_copy.data(), "destination") == 0);

  /* Same sandbox domain and valid bytes, but the trusted allocation metadata
   * says this pointer belongs to a different type. Extended SP3 rejects it. */
  auto wrong_ctx = sandbox.invoke_sandbox_function(interspec_popt_parse_smoke);
  REQUIRE(wrong_ctx.UNSAFE_unverified() != nullptr);
  auto wrong_arg =
    sandbox.invoke_sandbox_function(interspec_popt_get_opt_arg_wrong_type,
                                    wrong_ctx);
  REQUIRE(wrong_arg.UNSAFE_unverified() != nullptr);
  const uintptr_t wrong_arg_ptr =
    sandbox.get_sandbox_impl()->sandbox_address(wrong_arg.UNSAFE_unverified());
  REQUIRE(check(runtime, wrong_arg_ptr, kUsePoptOptArgFirstByte) ==
          interspec::CheckResult::wrong_type);
  std::vector<char> rejected_wrong_type;
  REQUIRE(!popt_copy_checked_cstring(
    sandbox, runtime, wrong_arg, rejected_wrong_type));

  /* Ordinary U malloc is still inside the sandbox, so domain-only SP3 would
   * accept it. The typed allocator has no trusted record for it and rejects. */
  auto untracked_ctx =
    sandbox.invoke_sandbox_function(interspec_popt_parse_smoke);
  REQUIRE(untracked_ctx.UNSAFE_unverified() != nullptr);
  auto untracked_arg =
    sandbox.invoke_sandbox_function(interspec_popt_get_opt_arg_untracked,
                                    untracked_ctx);
  REQUIRE(untracked_arg.UNSAFE_unverified() != nullptr);
  const uintptr_t untracked_arg_ptr =
    sandbox.get_sandbox_impl()->sandbox_address(untracked_arg.UNSAFE_unverified());
  REQUIRE(check(runtime, untracked_arg_ptr, kUsePoptOptArgFirstByte) ==
          interspec::CheckResult::untracked);
  std::vector<char> rejected_untracked;
  REQUIRE(!popt_copy_checked_cstring(
    sandbox, runtime, untracked_arg, rejected_untracked));

  sandbox.destroy_sandbox();
}
