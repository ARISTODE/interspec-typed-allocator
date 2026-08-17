#include "typed_arena.h"

#include <cstdint>

extern "C" {
using poc_alloc_fn = unsigned char* (*)(uint32_t, uint64_t);
using poc_free_fn = int (*)(unsigned char*);
void typed_poc_init(poc_alloc_fn, poc_free_fn);
unsigned char* typed_poc_make_item();
unsigned char* typed_poc_make_other();
unsigned char* typed_poc_make_untracked();
int typed_poc_release(unsigned char*);
void typed_poc_release_untracked(unsigned char*);
}

using PocSandbox = rlbox::rlbox_sandbox<TestType>;

static interspec::TypedArena* poc_arena;
static rlbox::tainted<unsigned char*, TestType>* poc_backing;

static rlbox::tainted<unsigned char*, TestType> poc_allocate(
  PocSandbox&,
  rlbox::tainted<uint32_t, TestType> size,
  rlbox::tainted<uint64_t, TestType> type_hash)
{
  const uintptr_t ptr = poc_arena->allocate(size.UNSAFE_unverified(),
                                             type_hash.UNSAFE_unverified());
  if (!ptr) return nullptr;
  return *poc_backing + (ptr - poc_arena->base());
}

static rlbox::tainted<int, TestType> poc_release(
  PocSandbox&,
  rlbox::tainted<unsigned char*, TestType> ptr)
{
  return poc_arena->release(reinterpret_cast<uintptr_t>(ptr.UNSAFE_unverified()));
}

TEST_CASE("InterSpec typed allocation PoC", "[typed_allocator]")
{
  constexpr uint64_t kItem = interspec::type_hash("Item");
  constexpr size_t kArenaSize = 4096;

  PocSandbox sandbox;
  CreateSandbox(sandbox);

  auto backing = sandbox.template malloc_in_sandbox<unsigned char>(kArenaSize);
  interspec::TypedArena arena(
    reinterpret_cast<uintptr_t>(backing.UNSAFE_unverified()), kArenaSize);
  poc_arena = &arena;
  poc_backing = &backing;

  auto alloc_cb = sandbox.register_callback(poc_allocate);
  auto free_cb = sandbox.register_callback(poc_release);
  sandbox.invoke_sandbox_function(typed_poc_init, alloc_cb, free_cb);

  auto item = sandbox.invoke_sandbox_function(typed_poc_make_item);
  auto other = sandbox.invoke_sandbox_function(typed_poc_make_other);
  auto untracked = sandbox.invoke_sandbox_function(typed_poc_make_untracked);

  const uintptr_t item_ptr = reinterpret_cast<uintptr_t>(item.UNSAFE_unverified());
  const uintptr_t other_ptr = reinterpret_cast<uintptr_t>(other.UNSAFE_unverified());
  const uintptr_t untracked_ptr =
    reinterpret_cast<uintptr_t>(untracked.UNSAFE_unverified());

  REQUIRE(sandbox.is_pointer_in_sandbox_memory(item.UNSAFE_unverified()));
  REQUIRE(arena.check(item_ptr, 8, kItem) == interspec::CheckResult::ok);
  REQUIRE(arena.check(other_ptr, 8, kItem) == interspec::CheckResult::wrong_type);
  REQUIRE(arena.check(item_ptr, 9, kItem) ==
          interspec::CheckResult::out_of_bounds);
  REQUIRE(arena.check(item_ptr + 4, 4, kItem) == interspec::CheckResult::ok);
  REQUIRE(arena.check(item_ptr + 4, 5, kItem) ==
          interspec::CheckResult::out_of_bounds);

  REQUIRE(sandbox.is_pointer_in_sandbox_memory(untracked.UNSAFE_unverified()));
  REQUIRE(arena.check(untracked_ptr, 8, kItem) == interspec::CheckResult::untracked);

  REQUIRE(sandbox.invoke_sandbox_function(typed_poc_release, item)
            .UNSAFE_unverified() == 1);
  REQUIRE(arena.check(item_ptr, 8, kItem) == interspec::CheckResult::untracked);

  sandbox.invoke_sandbox_function(typed_poc_release_untracked, untracked);
  sandbox.free_in_sandbox(backing);
  sandbox.destroy_sandbox();
}
