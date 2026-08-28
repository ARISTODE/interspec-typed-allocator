#include "interspec/runtime.h"
#include "interspec_popt_t_policy.h"
#include "site_provenance.h"

#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

extern "C" {
using popt_release_fn = uint32_t (*)(uint32_t);
using popt_size_fn = uint32_t (*)(uint32_t);
using popt_realloc_fn = uint32_t (*)(uint32_t, uint32_t);
void interspec_popt_init_lifetime(uint32_t,
                                  popt_release_fn,
                                  popt_size_fn,
                                  popt_realloc_fn);
void* interspec_popt_parse_smoke();
char* interspec_popt_get_opt_arg(void*);
char* interspec_popt_get_opt_arg_wrong_type(void*);
char* interspec_popt_get_opt_arg_untracked(void*);
int interspec_popt_archive_seen();
}

using PoptSandbox = rlbox::rlbox_sandbox<TestType>;

static interspec::Runtime* popt_runtime;

static uintptr_t popt_allocate_for_callback_pc(PoptSandbox& sandbox,
                                               uint32_t size)
{
  auto* impl = sandbox.get_sandbox_impl();
  const uintptr_t pc = impl->callback_program_counter();
  uintptr_t result = popt_runtime->allocate_from_pc(size, pc);
  if (result) return result;

  const uintptr_t new_pc = impl->callback_new_program_counter();
  if (new_pc && new_pc != pc)
    result = popt_runtime->allocate_from_pc(size, new_pc);
  return result;
}

static rlbox::tainted<uint32_t, TestType> popt_allocate(
  PoptSandbox& sandbox,
  rlbox::tainted<uint32_t, TestType> size)
{
  return static_cast<uint32_t>(
    popt_allocate_for_callback_pc(sandbox, size.UNSAFE_unverified()));
}

static rlbox::tainted<uint32_t, TestType> popt_release(
  PoptSandbox&,
  rlbox::tainted<uint32_t, TestType> ptr)
{
  return popt_runtime->release(ptr.UNSAFE_unverified()) ? 1u : 0u;
}

static rlbox::tainted<uint32_t, TestType> popt_size(
  PoptSandbox&,
  rlbox::tainted<uint32_t, TestType> ptr)
{
  size_t size = 0;
  if (!popt_runtime->allocation_size(ptr.UNSAFE_unverified(), size)) return 0u;
  if (size > std::numeric_limits<uint32_t>::max()) return 0u;
  return static_cast<uint32_t>(size);
}

static rlbox::tainted<uint32_t, TestType> popt_reallocate(
  PoptSandbox&,
  rlbox::tainted<uint32_t, TestType> ptr,
  rlbox::tainted<uint32_t, TestType> size)
{
  return static_cast<uint32_t>(popt_runtime->reallocate(
    ptr.UNSAFE_unverified(), size.UNSAFE_unverified()));
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

  auto resolve_symbol = [&](const char* name) -> uintptr_t {
    return sandbox.get_sandbox_impl()->lookup_symbol_address(name);
  };
  REQUIRE(register_allocation_sites(runtime, resolve_symbol));
  REQUIRE(runtime.register_allocation_site(
    INTERSPEC_POPT_STRDUP_SITE_ID,
    resolve_symbol(INTERSPEC_POPT_STRDUP_BEGIN_SYMBOL),
    resolve_symbol(INTERSPEC_POPT_STRDUP_END_SYMBOL),
    kTypeIdChar));

  auto alloc_cb = sandbox.register_callback(popt_allocate);
  auto release_cb = sandbox.register_callback(popt_release);
  auto size_cb = sandbox.register_callback(popt_size);
  auto realloc_cb = sandbox.register_callback(popt_reallocate);
  const uint32_t alloc_slot = sandbox.get_sandbox_impl()->callback_slot_for_key(
    reinterpret_cast<const void*>(popt_allocate));
  REQUIRE(alloc_slot != std::numeric_limits<uint32_t>::max());
  sandbox.invoke_sandbox_function(interspec_popt_init_lifetime,
                                  alloc_slot,
                                  release_cb,
                                  size_cb,
                                  realloc_cb);

  auto ctx = sandbox.invoke_sandbox_function(interspec_popt_parse_smoke);
  REQUIRE(ctx.UNSAFE_unverified() != nullptr);
  REQUIRE(sandbox.invoke_sandbox_function(interspec_popt_archive_seen)
            .UNSAFE_unverified() == 1);

  REQUIRE(runtime.allocation_count() >= 2);

  const uintptr_t ctx_ptr =
    sandbox.get_sandbox_impl()->sandbox_address(ctx.UNSAFE_unverified());
  REQUIRE(runtime.check(ctx_ptr, 1, kTypeHashPoptContextS) ==
          interspec::CheckResult::ok);
  interspec::SiteId ctx_site = 0;
  REQUIRE(runtime.allocation_site(ctx_ptr, ctx_site));
  REQUIRE(ctx_site != 0);

  auto arg = sandbox.invoke_sandbox_function(interspec_popt_get_opt_arg, ctx);
  REQUIRE(arg.UNSAFE_unverified() != nullptr);

  std::vector<char> trusted_copy;
  REQUIRE(popt_copy_checked_cstring(sandbox, runtime, arg, trusted_copy));
  REQUIRE(trusted_copy.size() == sizeof("destination"));
  REQUIRE(std::strcmp(trusted_copy.data(), "destination") == 0);

  /* A genuine authorized poptContext allocation cannot be relabeled as char. */
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
